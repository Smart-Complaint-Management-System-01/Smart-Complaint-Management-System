from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse

from accounts.decorators import admin_required

User = get_user_model()


@admin_required
def sample_admin_view(request):
    return HttpResponse("secret")


class RoleTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="u@x.com", email="u@x.com", password="Pass12345!")
        self.admin = User.objects.create_user(
            username="a@x.com", email="a@x.com", password="Pass12345!", role=User.Role.ADMIN
        )

    def test_default_role_is_user(self):
        self.assertEqual(self.user.role, User.Role.USER)
        self.assertFalse(self.user.is_admin_role)

    def test_admin_role(self):
        self.assertTrue(self.admin.is_admin_role)

    def test_superuser_is_always_admin(self):
        su = User.objects.create_superuser(username="root", email="root@x.com", password="Pass12345!")
        self.assertEqual(su.role, User.Role.ADMIN)

    def _request(self, user=None):
        request = self.factory.get("/x/")
        request.user = user or AnonymousUser()
        return request

    def test_decorator_anonymous_redirects_to_login(self):
        self.assertEqual(sample_admin_view(self._request()).status_code, 302)

    def test_decorator_user_denied(self):
        with self.assertRaises(PermissionDenied):
            sample_admin_view(self._request(self.user))

    def test_decorator_admin_allowed(self):
        self.assertEqual(sample_admin_view(self._request(self.admin)).status_code, 200)

    def test_dashboard_redirects_by_role(self):
        self.client.force_login(self.user)
        self.assertRedirects(self.client.get(reverse("accounts:dashboard")), reverse("complaints:my_list"), fetch_redirect_response=False)
        self.client.force_login(self.admin)
        self.assertRedirects(self.client.get(reverse("accounts:dashboard")), reverse("complaints:admin_list"), fetch_redirect_response=False)