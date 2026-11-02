from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from complaints.models import Complaint, ComplaintHistory
from complaints.services import InvalidTransition, change_status, resolve_complaint

User = get_user_model()

S = Complaint.Status


def make_user(email, role=User.Role.USER):
    return User.objects.create_user(username=email, email=email, password=None, role=role)


def make_complaint(user, status=S.IN_PROGRESS):
    return Complaint.objects.create(
        user=user,
        category=Complaint.Category.OTHER,
        title="Test complaint",
        description="A description long enough.",
        status=status,
    )


class ResolveComplaintServiceTests(TestCase):
    """Unit tests for resolve_complaint() service function (FR-10)."""

    @classmethod
    def setUpTestData(cls):
        cls.user = make_user("u@res.com")
        cls.admin = make_user("a@res.com", role=User.Role.ADMIN)

    def setUp(self):
        # Fresh IN_PROGRESS complaint for every test
        self.complaint = make_complaint(self.user)

    # --- input validation ---

    def test_empty_resolution_text_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            resolve_complaint(self.complaint, "", actor=self.admin)
        self.assertEqual(str(ctx.exception), "Please enter the resolution details.")

    def test_whitespace_only_resolution_text_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            resolve_complaint(self.complaint, "   ", actor=self.admin)
        self.assertEqual(str(ctx.exception), "Please enter the resolution details.")

    def test_none_resolution_text_raises_value_error(self):
        with self.assertRaises(ValueError):
            resolve_complaint(self.complaint, None, actor=self.admin)

    # --- status guard ---

    def test_non_in_progress_complaint_raises_invalid_transition(self):
        for status in (S.SUBMITTED, S.UNDER_REVIEW, S.ASSIGNED, S.REJECTED, S.CLOSED):
            with self.subTest(status=status):
                c = make_complaint(self.user, status=status)
                with self.assertRaises(InvalidTransition) as ctx:
                    resolve_complaint(c, "Fixed.", actor=self.admin)
                self.assertEqual(
                    str(ctx.exception),
                    "Only complaints that are In Progress can be resolved.",
                )

    def test_already_resolved_complaint_raises_invalid_transition(self):
        resolved = make_complaint(self.user, status=S.RESOLVED)
        with self.assertRaises(InvalidTransition) as ctx:
            resolve_complaint(resolved, "Fixed again.", actor=self.admin)
        self.assertEqual(
            str(ctx.exception),
            "Only complaints that are In Progress can be resolved.",
        )

    # --- successful resolution ---

    def test_successful_resolution_sets_status_to_resolved(self):
        resolve_complaint(self.complaint, "Fixed the issue.", actor=self.admin)
        self.complaint.refresh_from_db()
        self.assertEqual(self.complaint.status, S.RESOLVED)

    def test_successful_resolution_saves_trimmed_resolution_details(self):
        resolve_complaint(self.complaint, "  Fixed the issue.  ", actor=self.admin)
        self.complaint.refresh_from_db()
        self.assertEqual(self.complaint.resolution_details, "Fixed the issue.")

    def test_successful_resolution_sets_resolved_at_timestamp(self):
        resolve_complaint(self.complaint, "Fixed the issue.", actor=self.admin)
        self.complaint.refresh_from_db()
        self.assertIsNotNone(self.complaint.resolved_at)

    def test_successful_resolution_returns_updated_complaint(self):
        result = resolve_complaint(self.complaint, "Fixed.", actor=self.admin)
        self.assertEqual(result.pk, self.complaint.pk)
        self.assertEqual(result.status, S.RESOLVED)

    # --- history entry ---

    def test_successful_resolution_creates_one_history_entry(self):
        before = ComplaintHistory.objects.filter(complaint=self.complaint).count()
        resolve_complaint(self.complaint, "Fixed.", actor=self.admin)
        after = ComplaintHistory.objects.filter(complaint=self.complaint).count()
        self.assertEqual(after - before, 1)

    def test_history_entry_has_correct_new_status(self):
        resolve_complaint(self.complaint, "Fixed.", actor=self.admin)
        entry = ComplaintHistory.objects.get(complaint=self.complaint)
        self.assertEqual(entry.new_status, S.RESOLVED)

    def test_history_entry_has_correct_previous_status(self):
        resolve_complaint(self.complaint, "Fixed.", actor=self.admin)
        entry = ComplaintHistory.objects.get(complaint=self.complaint)
        self.assertEqual(entry.previous_status, S.IN_PROGRESS)

    def test_history_entry_records_resolution_text_in_details(self):
        resolve_complaint(self.complaint, "Fixed the issue.", actor=self.admin)
        entry = ComplaintHistory.objects.get(complaint=self.complaint)
        self.assertEqual(entry.update_details, "Resolved: Fixed the issue.")

    def test_history_entry_records_correct_actor(self):
        resolve_complaint(self.complaint, "Fixed.", actor=self.admin)
        entry = ComplaintHistory.objects.get(complaint=self.complaint)
        self.assertEqual(entry.updated_by, self.admin)

    # --- change_status() guard ---

    def test_change_status_rejects_direct_transition_to_resolved(self):
        with self.assertRaises(InvalidTransition) as ctx:
            change_status(self.complaint, S.RESOLVED, actor=self.admin)
        self.assertEqual(
            str(ctx.exception),
            "Record the resolution details to resolve a complaint.",
        )

    def test_change_status_to_resolved_does_not_modify_complaint(self):
        with self.assertRaises(InvalidTransition):
            change_status(self.complaint, S.RESOLVED, actor=self.admin)
        self.complaint.refresh_from_db()
        self.assertEqual(self.complaint.status, S.IN_PROGRESS)

    def test_change_status_to_resolved_creates_no_history_entry(self):
        before = ComplaintHistory.objects.filter(complaint=self.complaint).count()
        with self.assertRaises(InvalidTransition):
            change_status(self.complaint, S.RESOLVED, actor=self.admin)
        after = ComplaintHistory.objects.filter(complaint=self.complaint).count()
        self.assertEqual(before, after)

    # --- transaction rollback ---

    def test_resolution_rolls_back_if_history_creation_fails(self):
        from unittest.mock import patch
        with patch(
            "complaints.services.ComplaintHistory.objects.create",
            side_effect=Exception("db error"),
        ):
            with self.assertRaises(Exception):
                resolve_complaint(self.complaint, "Fixed.", actor=self.admin)
        self.complaint.refresh_from_db()
        self.assertEqual(self.complaint.status, S.IN_PROGRESS)
        self.assertEqual(self.complaint.resolution_details, "")
        self.assertIsNone(self.complaint.resolved_at)
        self.assertEqual(ComplaintHistory.objects.filter(complaint=self.complaint).count(), 0)

    # --- repeated resolution attempt ---

    def test_repeated_resolution_is_rejected_and_leaves_original_intact(self):
        resolve_complaint(self.complaint, "First fix.", actor=self.admin)
        self.complaint.refresh_from_db()
        original_details = self.complaint.resolution_details
        original_resolved_at = self.complaint.resolved_at
        history_count = ComplaintHistory.objects.filter(complaint=self.complaint).count()

        with self.assertRaises(InvalidTransition):
            resolve_complaint(self.complaint, "Second fix.", actor=self.admin)

        self.complaint.refresh_from_db()
        self.assertEqual(self.complaint.resolution_details, original_details)
        self.assertEqual(self.complaint.resolved_at, original_resolved_at)
        self.assertEqual(
            ComplaintHistory.objects.filter(complaint=self.complaint).count(),
            history_count,
        )


class AdminResolveViewTests(TestCase):
    """Integration tests for the admin_resolve view (FR-10)."""

    @classmethod
    def setUpTestData(cls):
        cls.user = make_user("vu@res.com")
        cls.admin = make_user("va@res.com", role=User.Role.ADMIN)

    def setUp(self):
        self.complaint = make_complaint(self.user)
        self.url = reverse("complaints:admin_resolve", args=[self.complaint.pk])

    # --- successful POST ---

    def test_successful_post_redirects_to_admin_detail(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.url, {"resolution_text": "All fixed."})
        self.assertRedirects(
            response,
            reverse("complaints:admin_detail", args=[self.complaint.pk]),
        )

    def test_successful_post_displays_success_message(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            self.url, {"resolution_text": "All fixed."}, follow=True
        )
        self.assertContains(response, "Complaint marked as resolved.")

    def test_successful_post_resolves_the_complaint(self):
        self.client.force_login(self.admin)
        self.client.post(self.url, {"resolution_text": "All fixed."})
        self.complaint.refresh_from_db()
        self.assertEqual(self.complaint.status, S.RESOLVED)
        self.assertEqual(self.complaint.resolution_details, "All fixed.")
        self.assertIsNotNone(self.complaint.resolved_at)

    # --- invalid POST ---

    def test_empty_resolution_text_displays_error_message(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            self.url, {"resolution_text": ""}, follow=True
        )
        self.assertContains(response, "Please enter the resolution details.")

    def test_empty_resolution_text_does_not_modify_complaint(self):
        self.client.force_login(self.admin)
        self.client.post(self.url, {"resolution_text": ""})
        self.complaint.refresh_from_db()
        self.assertEqual(self.complaint.status, S.IN_PROGRESS)

    def test_empty_resolution_text_creates_no_history_entry(self):
        self.client.force_login(self.admin)
        before = ComplaintHistory.objects.filter(complaint=self.complaint).count()
        self.client.post(self.url, {"resolution_text": ""})
        after = ComplaintHistory.objects.filter(complaint=self.complaint).count()
        self.assertEqual(before, after)

    def test_wrong_status_displays_error_message(self):
        self.complaint.status = S.SUBMITTED
        self.complaint.save(update_fields=["status", "updated_at"])
        self.client.force_login(self.admin)
        response = self.client.post(
            self.url, {"resolution_text": "Fixed."}, follow=True
        )
        self.assertContains(response, "Only complaints that are In Progress can be resolved.")

    def test_wrong_status_does_not_modify_complaint(self):
        self.complaint.status = S.SUBMITTED
        self.complaint.save(update_fields=["status", "updated_at"])
        self.client.force_login(self.admin)
        self.client.post(self.url, {"resolution_text": "Fixed."})
        self.complaint.refresh_from_db()
        self.assertEqual(self.complaint.status, S.SUBMITTED)

    def test_invalid_post_redirects_to_admin_detail(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.url, {"resolution_text": ""})
        self.assertRedirects(
            response,
            reverse("complaints:admin_detail", args=[self.complaint.pk]),
        )

    # --- authorization ---

    def test_regular_user_gets_403(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, {"resolution_text": "Fixed."})
        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_user_is_redirected(self):
        response = self.client.post(self.url, {"resolution_text": "Fixed."})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_get_request_is_rejected(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)


class AdminDetailResolutionDisplayTests(TestCase):
    """Integration tests: resolved complaint details visible on admin detail page."""

    @classmethod
    def setUpTestData(cls):
        cls.user = make_user("du@res.com")
        cls.admin = make_user("da@res.com", role=User.Role.ADMIN)

    def setUp(self):
        self.complaint = make_complaint(self.user)
        resolve_complaint(self.complaint, "Issue fully resolved.", actor=self.admin)
        self.complaint.refresh_from_db()
        self.detail_url = reverse("complaints:admin_detail", args=[self.complaint.pk])

    def test_admin_detail_displays_resolution_details(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Issue fully resolved.")

    def test_admin_detail_displays_resolved_at_timestamp(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.detail_url)
        # Extract the rendered timestamp from the template using the same
        # |date filter the template uses, so timezone handling is consistent.
        from django.template import Context, Template
        rendered = Template('{{ ts|date:"d M Y, H:i" }}').render(
            Context({"ts": self.complaint.resolved_at})
        )
        self.assertContains(response, rendered)
