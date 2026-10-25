from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.test import Client, TestCase
from django.urls import reverse

from complaints.models import Complaint

User = get_user_model()


class LogoutTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="u@x.com", email="u@x.com", password="Pass12345!")
        cls.admin = User.objects.create_user(
            username="a@x.com", email="a@x.com", password="Pass12345!", role=User.Role.ADMIN
        )
        cls.complaint = Complaint.objects.create(
            user=cls.user, category="OTHER", title="Title", description="d" * 30
        )
        cls.logout_url = reverse("accounts:logout")
        cls.login_url = reverse("accounts:login")

    # Criterion 1: users can log out
    def test_user_can_log_out_and_is_redirected_home(self):
        self.client.force_login(self.user)
        response = self.client.post(self.logout_url)
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_requires_post(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.logout_url).status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)  # still logged in

    # Criterion 2: logout invalidates the session
    def test_session_record_is_deleted_on_logout(self):
        self.client.force_login(self.user)
        old_key = self.client.cookies[settings.SESSION_COOKIE_NAME].value
        self.assertTrue(Session.objects.filter(session_key=old_key).exists())
        self.client.post(self.logout_url)
        self.assertFalse(Session.objects.filter(session_key=old_key).exists())

    # Criterion 3: the old session cannot be reused
    def test_old_session_cookie_cannot_access_protected_pages(self):
        self.client.force_login(self.user)
        old_key = self.client.cookies[settings.SESSION_COOKIE_NAME].value
        self.client.post(self.logout_url)

        replay = Client()  # a different browser replaying the stolen/old cookie
        replay.cookies[settings.SESSION_COOKIE_NAME] = old_key
        response = replay.get(reverse("accounts:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith(self.login_url))

    def test_old_admin_session_cannot_open_admin_pages_or_change_status(self):
        self.client.force_login(self.admin)
        old_key = self.client.cookies[settings.SESSION_COOKIE_NAME].value
        self.client.post(self.logout_url)

        replay = Client()
        replay.cookies[settings.SESSION_COOKIE_NAME] = old_key
        list_response = replay.get(reverse("complaints:admin_list"))
        self.assertEqual(list_response.status_code, 302)
        post_response = replay.post(
            reverse("complaints:admin_update_status", args=[self.complaint.pk]),
            {"status": "UNDER_REVIEW"},
        )
        self.assertEqual(post_response.status_code, 302)
        self.complaint.refresh_from_db()
        self.assertEqual(self.complaint.status, Complaint.Status.SUBMITTED)

    # Criterion 4: must authenticate again
    def test_after_logout_protected_page_redirects_to_login(self):
        self.client.force_login(self.user)
        self.client.post(self.logout_url)
        response = self.client.get(reverse("accounts:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith(self.login_url))

    def test_logout_when_already_logged_out_is_harmless(self):
        response = self.client.post(self.logout_url)
        self.assertEqual(response.status_code, 302)