from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from complaints.models import Complaint

User = get_user_model()


class AdminAuthorizationTests(TestCase):
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
            user=cls.user, category="OTHER", title="Title", description="d" * 30
        )

    def admin_get_urls(self):
        return [
            reverse("complaints:admin_list"),
            reverse("complaints:admin_detail", args=[self.complaint.pk]),
        ]

    def status_url(self):
        return reverse("complaints:admin_update_status", args=[self.complaint.pk])

    def test_regular_user_gets_403_on_every_admin_page(self):
        self.client.force_login(self.user)
        for url in self.admin_get_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_regular_user_cannot_change_status_with_a_direct_post(self):
        self.client.force_login(self.user)
        response = self.client.post(self.status_url(), {"status": "UNDER_REVIEW"})
        self.assertEqual(response.status_code, 403)
        self.complaint.refresh_from_db()
        self.assertEqual(self.complaint.status, Complaint.Status.SUBMITTED)

    def test_403_page_is_friendly(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("complaints:admin_list"))
        self.assertContains(response, "Access denied", status_code=403)

    def test_admin_is_allowed(self):
        self.client.force_login(self.admin)
        for url in self.admin_get_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_role_cannot_be_escalated_through_registration(self):
        self.client.post(reverse("accounts:register"), {
            "full_name": "Eve",
            "email": "eve@x.com",
            "password1": "Str0ngPass!23",
            "password2": "Str0ngPass!23",
            "role": "ADMIN",
            "is_staff": "on",
            "is_superuser": "on",
        })
        eve = User.objects.get(email="eve@x.com")
        self.assertEqual(eve.role, User.Role.USER)
        self.assertFalse(eve.is_staff)
        self.assertFalse(eve.is_superuser)