"""Branch-coverage tests for the complaints app.

Covers decision paths not exercised by the feature suites: model string
representations, assignment validation (FR-09), invalid admin form posts
(FR-07 / FR-09), submission-token and save-failure paths (NFR-04), the
seed_departments command and the placeholder view.
"""
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError
from django.test import RequestFactory, TestCase
from django.urls import reverse

from complaints.forms import AssignmentForm
from complaints.models import Complaint, ComplaintHistory, Department, Notification
from complaints.services import InvalidAssignment, assign_complaint
from config.views import coming_soon

User = get_user_model()
S = Complaint.Status


class BaseData(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="student", email="student@example.com", password=None,
            first_name="Stu", last_name="Dent",
        )
        self.admin = User.objects.create_user(
            username="admin", email="admin@example.com", password=None,
            role=User.Role.ADMIN, first_name="Ada", last_name="Min",
        )
        self.dept = Department.objects.create(name="Transport Office")
        self.complaint = Complaint.objects.create(
            user=self.user, category=Complaint.Category.TRANSPORT,
            title="Bus late", description="Route 5 bus is always late.",
            status=S.UNDER_REVIEW,
        )


class ModelStringTests(BaseData):
    def test_department_str(self):
        self.assertEqual(str(self.dept), "Transport Office")

    def test_complaint_str_uses_generated_id(self):
        self.assertEqual(str(self.complaint), f"{self.complaint.complaint_id} - Bus late")
        self.assertTrue(self.complaint.complaint_id.startswith("CMP-"))

    def test_unsaved_complaint_str_shows_new(self):
        self.assertEqual(str(Complaint(title="Draft")), "NEW - Draft")

    def test_assigned_label_variants(self):
        c = self.complaint
        self.assertEqual(c.assigned_label, "")
        c.assigned_to = self.admin
        self.assertEqual(c.assigned_label, "Ada Min")
        c.assigned_department = self.dept
        self.assertEqual(c.assigned_label, "Ada Min / Transport Office")
        c.assigned_to = None
        self.assertEqual(c.assigned_label, "Transport Office")

    def test_assigned_label_falls_back_to_email(self):
        nameless = User.objects.create_user(
            username="n", email="n@example.com", role=User.Role.ADMIN
        )
        self.complaint.assigned_to = nameless
        self.assertEqual(self.complaint.assigned_label, "n@example.com")

    def test_history_str_with_and_without_previous_status(self):
        first = ComplaintHistory.objects.create(complaint=self.complaint, new_status=S.SUBMITTED)
        second = ComplaintHistory.objects.create(
            complaint=self.complaint, previous_status=S.SUBMITTED, new_status=S.UNDER_REVIEW
        )
        cid = self.complaint.complaint_id
        self.assertEqual(str(first), f"{cid}: — → SUBMITTED")
        self.assertEqual(str(second), f"{cid}: SUBMITTED → UNDER_REVIEW")

    def test_notification_str(self):
        n = Notification.objects.create(user=self.user, complaint=self.complaint, message="Status changed")
        self.assertEqual(str(n), "Status changed")


class AssignmentValidationTests(BaseData):
    """FR-09: guard clauses in AssignmentForm and assign_complaint."""

    def test_form_requires_admin_or_department(self):
        form = AssignmentForm(data={})
        self.assertFalse(form.is_valid())
        self.assertIn("Select an administrator, a department, or both.", form.non_field_errors())

    def test_form_accepts_department_only(self):
        self.assertTrue(AssignmentForm(data={"department": self.dept.pk}).is_valid())

    def test_service_rejects_empty_assignment(self):
        with self.assertRaises(InvalidAssignment):
            assign_complaint(self.complaint, actor=self.admin)

    def test_service_rejects_non_admin_assignee(self):
        with self.assertRaisesRegex(InvalidAssignment, "active administrator"):
            assign_complaint(self.complaint, assigned_to=self.user, actor=self.admin)

    def test_service_rejects_inactive_admin(self):
        self.admin.is_active = False
        self.admin.save()
        with self.assertRaisesRegex(InvalidAssignment, "active administrator"):
            assign_complaint(self.complaint, assigned_to=self.admin, actor=self.admin)

    def test_department_only_assignment_records_none_admin(self):
        assign_complaint(self.complaint, department=self.dept, actor=self.admin)
        self.complaint.refresh_from_db()
        self.assertEqual(self.complaint.status, S.ASSIGNED)
        self.assertIn("Administrator = None", self.complaint.history.last().update_details)

    def test_reassignment_keeps_in_progress_status(self):
        self.complaint.status = S.IN_PROGRESS
        self.complaint.save()
        assign_complaint(self.complaint, assigned_to=self.admin, actor=self.admin)
        self.complaint.refresh_from_db()
        self.assertEqual(self.complaint.status, S.IN_PROGRESS)


class AdminViewErrorBranchTests(BaseData):
    """FR-07 / FR-09: error paths of admin_assign and admin_add_update."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)
        self.detail_url = reverse("complaints:admin_detail", args=[self.complaint.pk])

    def _messages(self, response):
        return [str(m) for m in response.wsgi_request._messages]

    def test_assign_with_empty_form_shows_error(self):
        r = self.client.post(reverse("complaints:admin_assign", args=[self.complaint.pk]), {})
        self.assertRedirects(r, self.detail_url, fetch_redirect_response=False)
        self.assertIn("Select an administrator, a department, or both.", self._messages(r))
        self.complaint.refresh_from_db()
        self.assertIsNone(self.complaint.assigned_department)

    def test_assign_with_invalid_choice_shows_field_error(self):
        r = self.client.post(reverse("complaints:admin_assign", args=[self.complaint.pk]),
                             {"department": 99999})
        self.assertRedirects(r, self.detail_url, fetch_redirect_response=False)
        self.assertTrue(any("valid choice" in m for m in self._messages(r)))

    def test_assign_resolved_complaint_shows_service_error(self):
        self.complaint.status = S.RESOLVED
        self.complaint.save()
        r = self.client.post(reverse("complaints:admin_assign", args=[self.complaint.pk]),
                             {"department": self.dept.pk})
        self.assertIn("This complaint cannot be assigned in its current status.", self._messages(r))

    def test_assign_success_message(self):
        r = self.client.post(reverse("complaints:admin_assign", args=[self.complaint.pk]),
                             {"assigned_to": self.admin.pk, "department": self.dept.pk})
        self.assertIn("Complaint assigned successfully.", self._messages(r))

    def test_add_update_with_blank_note_shows_error(self):
        before = self.complaint.history.count()
        r = self.client.post(reverse("complaints:admin_add_update", args=[self.complaint.pk]), {"note": ""})
        self.assertRedirects(r, self.detail_url, fetch_redirect_response=False)
        self.assertIn("Please enter an update note.", self._messages(r))
        self.assertEqual(self.complaint.history.count(), before)

    def test_add_update_on_resolved_complaint_is_rejected(self):
        self.complaint.status = S.RESOLVED
        self.complaint.save()
        r = self.client.post(reverse("complaints:admin_add_update", args=[self.complaint.pk]),
                             {"note": "Following up"})
        self.assertIn("Resolved complaints cannot be updated.", self._messages(r))


class SubmissionTokenBranchTests(BaseData):
    """NFR-04: token mismatch and unrecoverable save failure in new_complaint."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        self.url = reverse("complaints:new")
        self.data = {"category": "HOSTEL", "title": "Fan broken", "description": "Room 12 fan broken."}

    def test_post_without_token_is_treated_as_duplicate(self):
        r = self.client.post(self.url, self.data)
        self.assertRedirects(r, reverse("complaints:my_list"), fetch_redirect_response=False)
        self.assertFalse(Complaint.objects.filter(title="Fan broken").exists())

    def test_post_with_stale_token_is_treated_as_duplicate(self):
        self.client.get(self.url)
        r = self.client.post(self.url, {**self.data, "form_token": "stale"})
        self.assertRedirects(r, reverse("complaints:my_list"), fetch_redirect_response=False)
        self.assertFalse(Complaint.objects.filter(title="Fan broken").exists())

    def test_integrity_error_without_existing_record_shows_error(self):
        self.client.get(self.url)
        token = self.client.session["complaint_form_token"]
        with mock.patch.object(Complaint, "save", side_effect=IntegrityError):
            r = self.client.post(self.url, {**self.data, "form_token": token})
        self.assertContains(r, "We couldn&#x27;t save your complaint", status_code=500)
        self.assertFalse(Complaint.objects.filter(title="Fan broken").exists())


class SeedDepartmentsCommandTests(TestCase):
    def test_creates_departments_and_is_idempotent(self):
        from complaints.management.commands.seed_departments import DEPARTMENTS

        Department.objects.filter(name__in=DEPARTMENTS).delete()
        out = StringIO()
        call_command("seed_departments", stdout=out)
        self.assertEqual(Department.objects.filter(name__in=DEPARTMENTS).count(), len(DEPARTMENTS))
        self.assertIn("Created Academic Affairs", out.getvalue())

        total = Department.objects.count()
        out = StringIO()
        call_command("seed_departments", stdout=out)
        self.assertEqual(Department.objects.count(), total)
        self.assertIn("Exists  Academic Affairs", out.getvalue())


class PlaceholderViewTests(TestCase):
    def test_coming_soon_returns_501(self):
        response = coming_soon(RequestFactory().get("/"))
        self.assertEqual(response.status_code, 501)
