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
            username="u@x.com", email="u@x.com", password="Pass12345!"
        )
        cls.admin = User.objects.create_user(
            username="a@x.com", email="a@x.com", password="Pass12345!",
            role=User.Role.ADMIN,
        )
        cls.complaint = Complaint.objects.create(
            user=cls.user, category="ACADEMIC", title="Test complaint",
            description="A description long enough.",
        )

    def test_record_initial_status_creates_one_entry(self):
        record_initial_status(self.complaint, actor=self.user)
        entry = ComplaintHistory.objects.filter(complaint=self.complaint).last()
        self.assertIsNone(entry.previous_status)
        self.assertEqual(entry.new_status, Complaint.Status.SUBMITTED)
        self.assertEqual(entry.changed_by, self.user)

    def test_change_status_records_history(self):
        record_initial_status(self.complaint, actor=self.user)
        change_status(self.complaint, Complaint.Status.UNDER_REVIEW, actor=self.admin)
        entries = list(ComplaintHistory.objects.filter(complaint=self.complaint).order_by("changed_at"))
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[1].previous_status, Complaint.Status.SUBMITTED)
        self.assertEqual(entries[1].new_status, Complaint.Status.UNDER_REVIEW)
        self.assertEqual(entries[1].changed_by, self.admin)

    def test_history_entry_has_timestamp(self):
        record_initial_status(self.complaint, actor=self.user)
        entry = ComplaintHistory.objects.filter(complaint=self.complaint).last()
        self.assertIsNotNone(entry.changed_at)

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


class ComplaintHistoryViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="u@h.com", email="u@h.com", password="Pass12345!"
        )
        self.other_user = User.objects.create_user(
            username="o@h.com", email="o@h.com", password="Pass12345!"
        )
        self.admin = User.objects.create_user(
            username="a@h.com", email="a@h.com", password="Pass12345!",
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

    def test_admin_history_shows_changed_by_email(self):
        change_status(self.complaint, Complaint.Status.UNDER_REVIEW, actor=self.admin)
        self.client.force_login(self.admin)
        response = self.client.get(self.admin_history_url)
        self.assertContains(response, self.admin.email)


class ComplaintSubmissionCreatesHistoryTests(TestCase):
    """Verify that submitting via the view creates the initial history entry."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="s@h.com", email="s@h.com", password="Pass12345!"
        )
        self.client.force_login(self.user)

    def test_submission_via_view_creates_initial_history(self):
        self.client.post(
            reverse("complaints:new"),
            {"category": "OTHER", "title": "My issue", "description": "Details here."},
        )
        complaint = Complaint.objects.get(user=self.user)
        entries = ComplaintHistory.objects.filter(complaint=complaint)
        self.assertEqual(entries.count(), 1)
        self.assertEqual(entries.first().new_status, Complaint.Status.SUBMITTED)
        self.assertIsNone(entries.first().previous_status)
