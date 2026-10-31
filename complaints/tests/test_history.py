from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from complaints.models import Complaint, ComplaintHistory
from complaints.services import InvalidTransition, change_status, record_initial_status

User = get_user_model()


class ComplaintHistoryModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="u@x.com", email="u@x.com", password=None
        )
        cls.admin = User.objects.create_user(
            username="a@x.com", email="a@x.com", password=None,
            role=User.Role.ADMIN,
        )
        cls.complaint = Complaint.objects.create(
            user=cls.user, category="ACADEMIC", title="Test complaint",
            description="A description long enough.",
        )

    def test_record_initial_status_creates_one_entry(self):
        record_initial_status(self.complaint, actor=self.user)
        entry = ComplaintHistory.objects.filter(complaint=self.complaint).last()
        self.assertEqual(entry.previous_status, "")
        self.assertEqual(entry.new_status, Complaint.Status.SUBMITTED)
        self.assertEqual(entry.updated_by, self.user)

    def test_record_initial_status_stores_default_details(self):
        record_initial_status(self.complaint, actor=self.user)
        entry = ComplaintHistory.objects.filter(complaint=self.complaint).last()
        self.assertEqual(entry.update_details, "Complaint submitted")

    def test_record_initial_status_accepts_custom_details(self):
        record_initial_status(self.complaint, actor=self.user, details="Lodged via web form")
        entry = ComplaintHistory.objects.filter(complaint=self.complaint).last()
        self.assertEqual(entry.update_details, "Lodged via web form")

    def test_change_status_records_history(self):
        record_initial_status(self.complaint, actor=self.user)
        change_status(self.complaint, Complaint.Status.UNDER_REVIEW, actor=self.admin)
        entries = list(ComplaintHistory.objects.filter(complaint=self.complaint).order_by("created_at"))
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[1].previous_status, Complaint.Status.SUBMITTED)
        self.assertEqual(entries[1].new_status, Complaint.Status.UNDER_REVIEW)
        self.assertEqual(entries[1].updated_by, self.admin)

    def test_change_status_stores_details(self):
        change_status(self.complaint, Complaint.Status.UNDER_REVIEW, actor=self.admin, details="Looking into it")
        entry = ComplaintHistory.objects.filter(complaint=self.complaint).last()
        self.assertEqual(entry.update_details, "Looking into it")

    def test_change_status_empty_details_by_default(self):
        change_status(self.complaint, Complaint.Status.UNDER_REVIEW, actor=self.admin)
        entry = ComplaintHistory.objects.filter(complaint=self.complaint).last()
        self.assertEqual(entry.update_details, "")

    def test_history_entry_has_timestamp(self):
        record_initial_status(self.complaint, actor=self.user)
        entry = ComplaintHistory.objects.filter(complaint=self.complaint).last()
        self.assertIsNotNone(entry.created_at)

    def test_invalid_transition_does_not_create_history(self):
        before = ComplaintHistory.objects.filter(complaint=self.complaint).count()
        with self.assertRaises(InvalidTransition):
            change_status(self.complaint, Complaint.Status.RESOLVED, actor=self.admin)
        after = ComplaintHistory.objects.filter(complaint=self.complaint).count()
        self.assertEqual(before, after)

    def test_no_duplicate_entry_when_status_unchanged(self):
        record_initial_status(self.complaint, actor=self.user)
        record_initial_status(self.complaint, actor=self.user)
        count = ComplaintHistory.objects.filter(complaint=self.complaint).count()
        self.assertEqual(count, 1)

    def test_status_update_rolls_back_if_history_creation_fails(self):
        from unittest.mock import patch
        record_initial_status(self.complaint, actor=self.user)
        original_status = self.complaint.status
        with patch(
            "complaints.services.ComplaintHistory.objects.create",
            side_effect=Exception("db error"),
        ):
            with self.assertRaises(Exception):
                change_status(self.complaint, Complaint.Status.UNDER_REVIEW, actor=self.admin)
        self.complaint.refresh_from_db()
        self.assertEqual(self.complaint.status, original_status)

    def test_update_details_persists_to_database(self):
        change_status(self.complaint, Complaint.Status.UNDER_REVIEW, actor=self.admin, details="Checked on site")
        entry = ComplaintHistory.objects.filter(complaint=self.complaint).last()
        entry.refresh_from_db()
        self.assertEqual(entry.update_details, "Checked on site")


class ComplaintHistoryViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="u@h.com", email="u@h.com", password=None
        )
        self.other_user = User.objects.create_user(
            username="o@h.com", email="o@h.com", password=None
        )
        self.admin = User.objects.create_user(
            username="a@h.com", email="a@h.com", password=None,
            role=User.Role.ADMIN,
        )
        self.complaint = Complaint.objects.create(
            user=self.user, category="HOSTEL", title="Leaky pipe",
            description="Water leaking from the pipe.",
        )
        record_initial_status(self.complaint, actor=self.user)
        self.history_url = reverse(
            "complaints:complaint_history", args=[self.complaint.complaint_id]
        )
        self.admin_history_url = reverse(
            "complaints:admin_complaint_history", args=[self.complaint.pk]
        )

    # --- User history view ---

    def test_user_can_view_own_complaint_history(self):
        self.client.force_login(self.user)
        response = self.client.get(self.history_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.complaint.complaint_id)
        self.assertContains(response, "Submitted")

    def test_user_cannot_view_another_users_history(self):
        self.client.force_login(self.other_user)
        response = self.client.get(self.history_url)
        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_user_is_redirected_from_history(self):
        response = self.client.get(self.history_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_admin_cannot_access_user_history_view(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.history_url)
        self.assertEqual(response.status_code, 403)

    def test_history_shows_status_change_entry(self):
        change_status(self.complaint, Complaint.Status.UNDER_REVIEW, actor=self.admin)
        self.client.force_login(self.user)
        response = self.client.get(self.history_url)
        self.assertContains(response, "Under Review")
        self.assertContains(response, "Submitted")

    def test_history_shows_four_column_headers(self):
        self.client.force_login(self.user)
        response = self.client.get(self.history_url)
        self.assertContains(response, "Date")
        self.assertContains(response, "Change")
        self.assertContains(response, "By")
        self.assertContains(response, "Details")

    def test_history_shows_update_details(self):
        change_status(self.complaint, Complaint.Status.UNDER_REVIEW, actor=self.admin, details="Reviewing now")
        self.client.force_login(self.user)
        response = self.client.get(self.history_url)
        self.assertContains(response, "Reviewing now")

    def test_history_shows_system_fallback_when_no_actor(self):
        change_status(self.complaint, Complaint.Status.UNDER_REVIEW, actor=None)
        self.client.force_login(self.user)
        response = self.client.get(self.history_url)
        self.assertContains(response, "System")

    def test_history_shows_initial_submission_details(self):
        self.client.force_login(self.user)
        response = self.client.get(self.history_url)
        self.assertContains(response, "Complaint submitted")

    # --- Admin history view ---

    def test_admin_can_view_complaint_history(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.admin_history_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.complaint.complaint_id)
        self.assertContains(response, "Submitted")

    def test_regular_user_cannot_access_admin_history_view(self):
        self.client.force_login(self.user)
        response = self.client.get(self.admin_history_url)
        self.assertEqual(response.status_code, 403)

    def test_admin_history_shows_updated_by_email(self):
        change_status(self.complaint, Complaint.Status.UNDER_REVIEW, actor=self.admin)
        self.client.force_login(self.admin)
        response = self.client.get(self.admin_history_url)
        self.assertContains(response, self.admin.email)

    def test_admin_history_shows_four_column_headers(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.admin_history_url)
        self.assertContains(response, "Date")
        self.assertContains(response, "Change")
        self.assertContains(response, "By")
        self.assertContains(response, "Details")

    def test_admin_history_shows_update_details(self):
        change_status(self.complaint, Complaint.Status.UNDER_REVIEW, actor=self.admin, details="Admin note")
        self.client.force_login(self.admin)
        response = self.client.get(self.admin_history_url)
        self.assertContains(response, "Admin note")

    def test_admin_history_shows_system_fallback_when_no_actor(self):
        change_status(self.complaint, Complaint.Status.UNDER_REVIEW, actor=None)
        self.client.force_login(self.admin)
        response = self.client.get(self.admin_history_url)
        self.assertContains(response, "System")


class AdminStatusUpdateViewHistoryTests(TestCase):
    """Regression tests: admin_update_status view creates exactly one history entry with the correct actor."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="vu@h.com", email="vu@h.com", password=None
        )
        self.admin = User.objects.create_user(
            username="va@h.com", email="va@h.com", password=None,
            role=User.Role.ADMIN,
        )
        self.complaint = Complaint.objects.create(
            user=self.user, category="OTHER", title="View test",
            description="Description for view regression test.",
        )
        self.update_url = reverse(
            "complaints:admin_update_status", args=[self.complaint.pk]
        )

    def test_successful_transition_creates_exactly_one_history_entry(self):
        """A single valid POST must produce exactly one new ComplaintHistory row."""
        before = ComplaintHistory.objects.filter(complaint=self.complaint).count()
        self.client.force_login(self.admin)
        self.client.post(self.update_url, {"status": "UNDER_REVIEW"})
        after = ComplaintHistory.objects.filter(complaint=self.complaint).count()
        self.assertEqual(after - before, 1)

    def test_history_entry_records_correct_actor(self):
        """The history entry created by the view must reference the logged-in admin."""
        self.client.force_login(self.admin)
        self.client.post(self.update_url, {"status": "UNDER_REVIEW"})
        entry = ComplaintHistory.objects.get(
            complaint=self.complaint, new_status=Complaint.Status.UNDER_REVIEW
        )
        self.assertEqual(entry.updated_by, self.admin)

    def test_history_entry_records_correct_previous_and_new_status(self):
        """The history entry must capture the transition from SUBMITTED to UNDER_REVIEW."""
        self.client.force_login(self.admin)
        self.client.post(self.update_url, {"status": "UNDER_REVIEW"})
        entry = ComplaintHistory.objects.get(
            complaint=self.complaint, new_status=Complaint.Status.UNDER_REVIEW
        )
        self.assertEqual(entry.previous_status, Complaint.Status.SUBMITTED)
        self.assertEqual(entry.new_status, Complaint.Status.UNDER_REVIEW)

    def test_invalid_transition_via_view_creates_no_history_entry(self):
        """A POST with an invalid status must not create a history entry."""
        before = ComplaintHistory.objects.filter(complaint=self.complaint).count()
        self.client.force_login(self.admin)
        self.client.post(self.update_url, {"status": "RESOLVED"})
        after = ComplaintHistory.objects.filter(complaint=self.complaint).count()
        self.assertEqual(before, after)

    def test_invalid_transition_via_view_does_not_change_complaint_status(self):
        """A POST with an invalid status must leave the complaint status unchanged."""
        self.client.force_login(self.admin)
        self.client.post(self.update_url, {"status": "RESOLVED"})
        self.complaint.refresh_from_db()
        self.assertEqual(self.complaint.status, Complaint.Status.SUBMITTED)


class ComplaintSubmissionCreatesHistoryTests(TestCase):
    """Verify that submitting via the view creates the initial history entry."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="s@h.com", email="s@h.com", password=None
        )
        self.client.force_login(self.user)
        self.url = reverse("complaints:new")

    def _submit(self):
        """Submit through the real view, including the NFR-04 one-time form token."""
        self.client.get(self.url)  # the GET issues the token into the session
        return self.client.post(
            self.url,
            {
                "category": "OTHER",
                "title": "My issue",
                "description": "Details here.",
                "form_token": self.client.session["complaint_form_token"],
            },
        )

    def test_submission_via_view_creates_initial_history(self):
        self._submit()
        complaint = Complaint.objects.get(user=self.user)
        entries = ComplaintHistory.objects.filter(complaint=complaint)
        self.assertEqual(entries.count(), 1)
        self.assertEqual(entries.first().new_status, Complaint.Status.SUBMITTED)
        self.assertEqual(entries.first().previous_status, "")

    def test_submission_via_view_stores_submitted_details(self):
        self._submit()
        complaint = Complaint.objects.get(user=self.user)
        entry = ComplaintHistory.objects.get(complaint=complaint)
        self.assertEqual(entry.update_details, "Complaint submitted")


class ComplaintDetailViewTests(TestCase):
    """P5: User-facing complaint detail page."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="d@h.com", email="d@h.com", password=None
        )
        self.other_user = User.objects.create_user(
            username="d2@h.com", email="d2@h.com", password=None
        )
        self.admin = User.objects.create_user(
            username="da@h.com", email="da@h.com", password=None,
            role=User.Role.ADMIN,
        )
        self.complaint = Complaint.objects.create(
            user=self.user, category="ACADEMIC", title="Detail test",
            description="Description for detail view test.",
        )
        record_initial_status(self.complaint, actor=self.user)
        self.detail_url = reverse(
            "complaints:complaint_detail", args=[self.complaint.complaint_id]
        )

    def test_user_can_view_own_complaint_detail(self):
        self.client.force_login(self.user)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.complaint.complaint_id)
        self.assertContains(response, self.complaint.title)

    def test_user_cannot_view_another_users_complaint_detail(self):
        self.client.force_login(self.other_user)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_user_is_redirected_from_detail(self):
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_admin_cannot_access_user_detail_view(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, 403)

    def test_detail_shows_history_entries(self):
        change_status(self.complaint, Complaint.Status.UNDER_REVIEW, actor=self.admin)
        self.client.force_login(self.user)
        response = self.client.get(self.detail_url)
        self.assertContains(response, "Under Review")
        self.assertContains(response, "Submitted")

    def test_detail_shows_complaint_description(self):
        self.client.force_login(self.user)
        response = self.client.get(self.detail_url)
        self.assertContains(response, self.complaint.description)

    def test_my_complaints_links_to_detail(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("complaints:my_list"))
        self.assertContains(
            response,
            reverse("complaints:complaint_detail", args=[self.complaint.complaint_id]),
        )
