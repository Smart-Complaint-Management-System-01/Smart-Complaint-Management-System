from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from complaints.models import Complaint


User = get_user_model()


class ComplaintSubmissionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="user@example.com",
            email="user@example.com",
            password="Pass12345!",
        )
        self.admin = User.objects.create_user(
            username="admin@example.com",
            email="admin@example.com",
            password="Pass12345!",
            role=User.Role.ADMIN,
        )
        self.url = reverse("complaints:new")

    def test_authenticated_user_can_open_form(self):
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lodge a Complaint")
        self.assertContains(response, 'name="category"')
        self.assertContains(response, 'name="title"')
        self.assertContains(response, 'name="description"')

    def test_valid_submission_redirects_to_owned_confirmation(self):
        self.client.force_login(self.user)

        response = self.client.post(
            self.url,
            {
                "category": Complaint.Category.ACADEMIC,
                "title": "Course materials",
                "description": "The course materials are unavailable.",
            },
        )

        self.assertEqual(response.status_code, 302)
        complaint = Complaint.objects.get()
        self.assertEqual(complaint.user, self.user)
        self.assertEqual(complaint.category, Complaint.Category.ACADEMIC)
        self.assertEqual(complaint.title, "Course materials")
        self.assertEqual(complaint.description, "The course materials are unavailable.")
        self.assertTrue(complaint.complaint_id.startswith("CMP-"))
        confirmation_url = reverse(
            "complaints:submission_confirmation", args=[complaint.complaint_id]
        )
        self.assertRedirects(response, confirmation_url, fetch_redirect_response=False)

        confirmation = self.client.get(confirmation_url)
        self.assertEqual(confirmation.status_code, 200)
        self.assertContains(confirmation, complaint.complaint_id)
        self.assertContains(confirmation, complaint.get_category_display())
        self.assertContains(confirmation, complaint.title)
        self.assertContains(confirmation, complaint.description)
        self.assertContains(confirmation, complaint.get_status_display())
        self.assertContains(confirmation, "Complaint submitted successfully")

    def test_user_cannot_view_another_users_submission_confirmation(self):
        complaint = Complaint.objects.create(
            user=self.admin,
            category=Complaint.Category.OTHER,
            title="Private complaint",
            description="Only the submitter can view this confirmation.",
        )
        self.client.force_login(self.user)
        url = reverse(
            "complaints:submission_confirmation", args=[complaint.complaint_id]
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_user_is_redirected_from_submission(self):
        response = self.client.post(self.url, {})

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])
        self.assertEqual(Complaint.objects.count(), 0)

    def test_admin_cannot_use_normal_submission_flow(self):
        self.client.force_login(self.admin)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Complaint.objects.count(), 0)

    def test_invalid_or_incomplete_input_does_not_create_complaint(self):
        self.client.force_login(self.user)

        response = self.client.post(
            self.url,
            {"category": Complaint.Category.ACADEMIC, "title": "", "description": ""},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Complaint.objects.count(), 0)
        self.assertContains(response, "This field is required.")

    def test_model_generates_unique_id_and_initial_status(self):
        first = Complaint.objects.create(
            user=self.user,
            category=Complaint.Category.OTHER,
            title="First",
            description="First complaint.",
        )
        second = Complaint.objects.create(
            user=self.user,
            category=Complaint.Category.OTHER,
            title="Second",
            description="Second complaint.",
        )

        self.assertNotEqual(first.complaint_id, second.complaint_id)
        self.assertTrue(first.complaint_id.startswith("CMP-"))
        self.assertEqual(first.status, Complaint.Status.SUBMITTED)
        self.assertEqual(second.status, Complaint.Status.SUBMITTED)
