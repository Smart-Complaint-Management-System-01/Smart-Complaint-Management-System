
from django.contrib.auth import get_user_model
from django.template import response
from django.test import TestCase
from django.urls import reverse

from complaints.models import Complaint


User = get_user_model()


class ComplaintValidationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="validationuser",
            email="validation@example.com",
            password=None,
        )
        self.client.force_login(self.user)
        self.url = reverse("complaints:new")

    def test_form_page_loads(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "complaints/new.html")

    def test_missing_fields_show_validation_errors(self):
        response = self.client.post(self.url, {})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please select a complaint category.")
        self.assertContains(response, "Please enter a complaint title.")
        self.assertContains(response,"Please enter a description of your complaint.",)
        self.assertEqual(Complaint.objects.count(), 0)

    def test_invalid_category_is_rejected(self):
        response = self.client.post(
            self.url,
            {
                "category": "INVALID_CATEGORY",
                "title": "Test complaint",
                "description": "This is a test complaint description.",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please select a valid complaint category.")
        self.assertEqual(Complaint.objects.count(), 0)

    def test_whitespace_only_title_is_rejected(self):
        response = self.client.post(
            self.url,
            {
                "category": Complaint.Category.ACADEMIC,
                "title": "   ",
                "description": "A valid complaint description.",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please enter a complaint title.")
        self.assertEqual(Complaint.objects.count(), 0)

    def test_whitespace_only_description_is_rejected(self):
        response = self.client.post(
            self.url,
            {
                "category": Complaint.Category.ACADEMIC,
                "title": "Valid title",
                "description": "   ",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Please enter a description of your complaint.",
        )
        self.assertEqual(Complaint.objects.count(), 0)

    def test_valid_submission_creates_complaint(self):
        response = self.client.post(
            self.url,
            {
                "category": Complaint.Category.ACADEMIC,
                "title": "Library computer issue",
                "description": "The computers in the library are not working.",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertRegex(response.url, r"^/complaints/.+/submitted/$")
        self.assertEqual(Complaint.objects.count(), 1)

        complaint = Complaint.objects.get()
        self.assertEqual(complaint.user, self.user)
        self.assertEqual(complaint.status, Complaint.Status.SUBMITTED)
