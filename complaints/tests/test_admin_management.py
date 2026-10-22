from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from complaints.models import Complaint
from complaints.services import InvalidTransition, change_status

User = get_user_model()


class AdminManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="u@x.com", email="u@x.com", password="Pass12345!")
        cls.admin = User.objects.create_user(username="a@x.com", email="a@x.com", password="Pass12345!", role=User.Role.ADMIN)
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