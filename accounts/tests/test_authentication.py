
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


User = get_user_model()


class AuthenticationTests(TestCase):
    def setUp(self):
        self.email = "test@example.com"
        self.password = "TestPassword123!"

        self.user = User.objects.create_user(
            username="testuser",
            email=self.email,
            password=self.password,
        )

    def test_login_page_loads(self):
        response = self.client.get(reverse("accounts:login"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/login.html")

    def test_login_with_valid_email_and_password(self):
        response = self.client.post(
            reverse("accounts:login"),
            {
                "email": self.email,
                "password": self.password,
            },
        )

        self.assertRedirects(response, reverse("accounts:dashboard"), fetch_redirect_response=False)
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_login_with_invalid_password(self):
        response = self.client.post(
            reverse("accounts:login"),
            {
                "email": self.email,
                "password": "WrongPassword123!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid email or password.")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_with_unknown_email(self):
        response = self.client.post(
            reverse("accounts:login"),
            {
                "email": "unknown@example.com",
                "password": self.password,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid email or password.")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("accounts:logout"))

        self.assertRedirects(response, reverse("home"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_rejects_get_request(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("accounts:logout"))

        self.assertEqual(response.status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)
