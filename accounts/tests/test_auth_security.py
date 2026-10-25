from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from complaints.models import Complaint

User = get_user_model()


class AuthenticationSecurityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            username="owner@example.com", email="owner@example.com", password="Pass12345!"
        )
        cls.complaint = Complaint.objects.create(
            user=cls.owner,
            category=Complaint.Category.OTHER,
            title="Protected complaint",
            description="Only the owner and administrators may see this.",
        )

    def protected_urls(self):
        return [
            reverse("complaints:my_list"),
            reverse("complaints:new"),
            reverse("complaints:submission_confirmation", args=[self.complaint.complaint_id]),
            reverse("complaints:admin_list"),
            reverse("complaints:admin_detail", args=[self.complaint.pk]),
            reverse("accounts:dashboard"),
        ]

    def test_anonymous_is_redirected_to_login_for_every_protected_url(self):
        for url in self.protected_urls():
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response["Location"].startswith(reverse("accounts:login")))
                self.assertIn("next=", response["Location"])

    def test_anonymous_post_to_admin_status_endpoint_is_denied(self):
        url = reverse("complaints:admin_update_status", args=[self.complaint.pk])
        response = self.client.post(url, {"status": "UNDER_REVIEW"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith(reverse("accounts:login")))
        self.complaint.refresh_from_db()
        self.assertEqual(self.complaint.status, Complaint.Status.SUBMITTED)

    def test_anonymous_post_to_submission_is_denied_and_creates_nothing(self):
        response = self.client.post(reverse("complaints:new"), {"title": "x"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Complaint.objects.count(), 1)

    def test_public_pages_stay_public(self):
        for name in ["home", "accounts:login", "accounts:register"]:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_django_admin_login_page_stays_reachable(self):
        self.assertEqual(self.client.get(reverse("admin:login")).status_code, 200)

    def test_failed_login_does_not_grant_access(self):
        self.client.post(
            reverse("accounts:login"),
            {"email": "owner@example.com", "password": "WrongPassword123!"},
        )
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(self.client.get(reverse("complaints:my_list")).status_code, 302)

    def test_authenticated_user_can_reach_protected_page(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse("complaints:my_list")).status_code, 200)