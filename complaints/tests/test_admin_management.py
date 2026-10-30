from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from complaints.models import Complaint, ComplaintHistory
from complaints.services import InvalidTransition, change_status

User = get_user_model()


class AdminManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="u@x.com", email="u@x.com", password=None)
        cls.admin = User.objects.create_user(username="a@x.com", email="a@x.com", password=None, role=User.Role.ADMIN)
        cls.complaint = Complaint.objects.create(
            user=cls.user, category="HOSTEL", title="Leaky tap", description="The tap has been leaking for a week."
        )

    def test_admin_sees_all_complaints(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("complaints:admin_list"))
        self.assertContains(response, self.complaint.complaint_id)
        self.assertContains(response, "u@x.com")

    def test_admin_can_open_detail(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("complaints:admin_detail", args=[self.complaint.pk]))
        self.assertContains(response, "Leaky tap")
        self.assertContains(response, "Move to")

    def test_admin_moves_status_one_step(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("complaints:admin_update_status", args=[self.complaint.pk]), {"status": "UNDER_REVIEW"})
        self.complaint.refresh_from_db()
        self.assertEqual(self.complaint.status, Complaint.Status.UNDER_REVIEW)

    def test_skipping_a_status_is_rejected(self):
        with self.assertRaises(InvalidTransition):
            change_status(self.complaint, "RESOLVED")
        self.complaint.refresh_from_db()
        self.assertEqual(self.complaint.status, Complaint.Status.SUBMITTED)

    def test_status_update_requires_post(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("complaints:admin_update_status", args=[self.complaint.pk]))
        self.assertEqual(response.status_code, 405)


class StatusTransitionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="tu@x.com", email="tu@x.com", password=None
        )
        cls.admin = User.objects.create_user(
            username="ta@x.com", email="ta@x.com", password=None,
            role=User.Role.ADMIN,
        )

    def make_complaint(self, status=Complaint.Status.SUBMITTED):
        return Complaint.objects.create(
            user=self.user, category="OTHER", title="T", description="D" * 20,
            status=status,
        )

    # --- valid transitions ---
    def test_submitted_to_under_review(self):
        c = self.make_complaint(Complaint.Status.SUBMITTED)
        change_status(c, Complaint.Status.UNDER_REVIEW, actor=self.admin)
        c.refresh_from_db()
        self.assertEqual(c.status, Complaint.Status.UNDER_REVIEW)

    def test_submitted_to_rejected(self):
        c = self.make_complaint(Complaint.Status.SUBMITTED)
        change_status(c, Complaint.Status.REJECTED, actor=self.admin)
        c.refresh_from_db()
        self.assertEqual(c.status, Complaint.Status.REJECTED)

    def test_under_review_to_assigned(self):
        c = self.make_complaint(Complaint.Status.UNDER_REVIEW)
        change_status(c, Complaint.Status.ASSIGNED, actor=self.admin)
        c.refresh_from_db()
        self.assertEqual(c.status, Complaint.Status.ASSIGNED)

    def test_under_review_to_rejected(self):
        c = self.make_complaint(Complaint.Status.UNDER_REVIEW)
        change_status(c, Complaint.Status.REJECTED, actor=self.admin)
        c.refresh_from_db()
        self.assertEqual(c.status, Complaint.Status.REJECTED)

    def test_resolved_to_closed(self):
        c = self.make_complaint(Complaint.Status.RESOLVED)
        change_status(c, Complaint.Status.CLOSED, actor=self.admin)
        c.refresh_from_db()
        self.assertEqual(c.status, Complaint.Status.CLOSED)

    def test_rejected_to_closed(self):
        c = self.make_complaint(Complaint.Status.REJECTED)
        change_status(c, Complaint.Status.CLOSED, actor=self.admin)
        c.refresh_from_db()
        self.assertEqual(c.status, Complaint.Status.CLOSED)

    # --- invalid transitions ---
    def test_closed_has_no_further_transitions(self):
        c = self.make_complaint(Complaint.Status.CLOSED)
        with self.assertRaises(InvalidTransition):
            change_status(c, Complaint.Status.RESOLVED, actor=self.admin)
        c.refresh_from_db()
        self.assertEqual(c.status, Complaint.Status.CLOSED)

    def test_rejected_cannot_reopen(self):
        c = self.make_complaint(Complaint.Status.REJECTED)
        with self.assertRaises(InvalidTransition):
            change_status(c, Complaint.Status.SUBMITTED, actor=self.admin)
        c.refresh_from_db()
        self.assertEqual(c.status, Complaint.Status.REJECTED)

    def test_skipping_submitted_to_resolved_is_invalid(self):
        c = self.make_complaint(Complaint.Status.SUBMITTED)
        with self.assertRaises(InvalidTransition):
            change_status(c, Complaint.Status.RESOLVED, actor=self.admin)

    # --- history recording for new transitions ---
    def test_rejection_records_history(self):
        c = self.make_complaint(Complaint.Status.SUBMITTED)
        change_status(c, Complaint.Status.REJECTED, actor=self.admin)
        entry = ComplaintHistory.objects.get(complaint=c, new_status=Complaint.Status.REJECTED)
        self.assertEqual(entry.previous_status, Complaint.Status.SUBMITTED)
        self.assertEqual(entry.updated_by, self.admin)

    def test_closed_from_rejected_records_history(self):
        c = self.make_complaint(Complaint.Status.REJECTED)
        change_status(c, Complaint.Status.CLOSED, actor=self.admin)
        entry = ComplaintHistory.objects.get(complaint=c, new_status=Complaint.Status.CLOSED)
        self.assertEqual(entry.previous_status, Complaint.Status.REJECTED)

    # --- admin detail template renders correct action buttons ---
    def test_admin_detail_shows_both_actions_for_submitted(self):
        c = self.make_complaint(Complaint.Status.SUBMITTED)
        self.client.force_login(self.admin)
        response = self.client.get(reverse("complaints:admin_detail", args=[c.pk]))
        self.assertContains(response, "Under Review")
        self.assertContains(response, "Rejected")

    def test_admin_detail_shows_both_actions_for_under_review(self):
        c = self.make_complaint(Complaint.Status.UNDER_REVIEW)
        self.client.force_login(self.admin)
        response = self.client.get(reverse("complaints:admin_detail", args=[c.pk]))
        self.assertContains(response, "Assigned")
        self.assertContains(response, "Rejected")

    def test_admin_detail_shows_no_actions_for_closed(self):
        c = self.make_complaint(Complaint.Status.CLOSED)
        self.client.force_login(self.admin)
        response = self.client.get(reverse("complaints:admin_detail", args=[c.pk]))
        self.assertContains(response, "No further status changes are available.")
        self.assertNotContains(response, "Move to")