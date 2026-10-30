
from django.contrib.auth import get_user_model
from django.template import response
from django.test import TestCase
from django.urls import reverse

from complaints.models import Complaint


User = get_user_model()


class ComplaintStatusTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="user1",
            email="user1@example.com",
            password=None,
        )

        self.other_user = User.objects.create_user(
            username="user2",
            email="user2@example.com",
            password=None,
        )

        self.complaint = Complaint.objects.create(
            user=self.user,
            category=Complaint.Category.ACADEMIC,
            title="Library issue",
            description="The library computers are not working.",
            status=Complaint.Status.UNDER_REVIEW,
        )

        self.other_complaint = Complaint.objects.create(
            user=self.other_user,
            category=Complaint.Category.HOSTEL,
            title="Hostel issue",
            description="The hostel water supply is interrupted.",
            status=Complaint.Status.SUBMITTED,
        )

    def test_login_required_for_complaint_list(self):
        response = self.client.get(reverse("complaints:my_list"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_user_can_view_own_complaints(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("complaints:my_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Library issue")
        self.assertContains(response, "Under Review")

    def test_user_cannot_view_other_users_complaints(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("complaints:my_list"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Hostel issue")
        self.assertNotContains(
            response,
            "The hostel water supply is interrupted.",
        )

    def test_complaint_status_is_displayed_correctly(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("complaints:my_list"))

        self.assertContains(response, self.complaint.complaint_id)
        self.assertContains(response, "Under Review")

    def test_empty_complaint_list(self):
        self.client.force_login(self.other_user)
        self.other_complaint.delete()

        response = self.client.get(reverse("complaints:my_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You haven't submitted any complaints yet.")