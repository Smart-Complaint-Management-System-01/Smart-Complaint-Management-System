"""Branch-coverage tests for the accounts app.

These cover decision paths not exercised by the feature test suites:
EmailBackend guard clauses, single-word names on registration,
login redirects (FR-02), the function-based logout view (NFR-10) and the
NFR-02 load-test seeding command.
"""
import csv
import tempfile
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from accounts.backends import EmailBackend
from accounts.forms import RegistrationForm
from accounts.views import logout_view

User = get_user_model()
PASSWORD = "Str0ng!Passw0rd"


class EmailBackendBranchTests(TestCase):
    """FR-02 / NFR-07: every early-return path of EmailBackend.authenticate."""

    def setUp(self):
        self.backend = EmailBackend()
        self.user = User.objects.create_user(
            username="alice", email="alice@example.com", password=PASSWORD
        )

    def test_missing_email_returns_none(self):
        self.assertIsNone(self.backend.authenticate(None, username=None, password=PASSWORD))

    def test_missing_password_returns_none(self):
        self.assertIsNone(self.backend.authenticate(None, username="alice@example.com", password=None))

    def test_email_keyword_is_accepted(self):
        self.assertEqual(
            self.backend.authenticate(None, email="alice@example.com", password=PASSWORD),
            self.user,
        )

    def test_email_lookup_is_case_insensitive(self):
        self.assertEqual(
            self.backend.authenticate(None, username="ALICE@Example.com", password=PASSWORD),
            self.user,
        )

    def test_unknown_email_returns_none(self):
        self.assertIsNone(self.backend.authenticate(None, username="nobody@example.com", password=PASSWORD))

    def test_wrong_password_returns_none(self):
        self.assertIsNone(self.backend.authenticate(None, username="alice@example.com", password="wrong"))

    def test_inactive_user_cannot_authenticate(self):
        self.user.is_active = False
        self.user.save()
        self.assertIsNone(self.backend.authenticate(None, username="alice@example.com", password=PASSWORD))


class RegistrationFormBranchTests(TestCase):
    """FR-01: full-name splitting and commit=False path."""

    def _form(self, full_name, email="bob@example.com"):
        return RegistrationForm(
            data={"full_name": full_name, "email": email,
                  "password1": PASSWORD, "password2": PASSWORD}
        )

    def test_single_word_name_leaves_last_name_blank(self):
        form = self._form("Bob")
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual((user.first_name, user.last_name), ("Bob", ""))

    def test_two_part_name_is_split(self):
        form = self._form("Bob Marley Jr")
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual((user.first_name, user.last_name), ("Bob", "Marley Jr"))

    def test_commit_false_does_not_save(self):
        form = self._form("Bob Builder")
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save(commit=False)
        self.assertIsNone(user.pk)
        self.assertFalse(User.objects.filter(email="bob@example.com").exists())


class LoginViewBranchTests(TestCase):
    """FR-02: redirect branches of login_view."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="carol", email="carol@example.com", password=PASSWORD
        )

    def test_authenticated_user_is_redirected_from_login(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("accounts:login"))
        self.assertRedirects(response, reverse("accounts:dashboard"), fetch_redirect_response=False)

    def test_safe_next_url_is_followed(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"email": "carol@example.com", "password": PASSWORD, "next": "/complaints/"},
        )
        self.assertRedirects(response, "/complaints/", fetch_redirect_response=False)

    def test_next_from_query_string_is_followed(self):
        response = self.client.post(
            reverse("accounts:login") + "?next=/notifications/",
            {"email": "carol@example.com", "password": PASSWORD},
        )
        self.assertRedirects(response, "/notifications/", fetch_redirect_response=False)

    def test_protocol_relative_next_is_rejected(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"email": "carol@example.com", "password": PASSWORD, "next": "//evil.example.com/"},
        )
        self.assertRedirects(response, reverse("accounts:dashboard"), fetch_redirect_response=False)

    def test_absolute_external_next_is_rejected(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"email": "carol@example.com", "password": PASSWORD, "next": "https://evil.example.com/"},
        )
        self.assertRedirects(response, reverse("accounts:dashboard"), fetch_redirect_response=False)


class LogoutViewFunctionTests(TestCase):
    """NFR-10: the function-based logout view clears the session."""

    def test_logout_view_logs_out_and_redirects_home(self):
        user = User.objects.create_user(username="dave", email="dave@example.com", password=PASSWORD)
        request = RequestFactory().post("/logout/")
        SessionMiddleware(lambda r: None).process_request(request)
        request.session.save()
        request.user = user
        request._messages = FallbackStorage(request)

        response = logout_view(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("home"))
        self.assertFalse(request.user.is_authenticated)


class SeedLoadTestUsersBranchTests(TestCase):
    """NFR-02 support command: create, refuse and cleanup paths."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.csv_path = self.base / "performance" / "test-users.csv"
        override = override_settings(BASE_DIR=self.base)
        override.enable()
        self.addCleanup(override.disable)

    def _seed(self, password="LoadTest#1"):
        with mock.patch("getpass.getpass", return_value=password):
            call_command("seed_load_test_users", confirm_local=True, count=100, stdout=mock.MagicMock())

    def test_creates_100_users_and_credentials_file(self):
        self._seed()
        self.assertEqual(User.objects.filter(email__endswith="@example.test").count(), 100)
        with self.csv_path.open(encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 100)
        self.assertEqual(rows[0]["email"], "nfr02-user-001@example.test")

    def test_refuses_to_overwrite_existing_credentials_file(self):
        self.csv_path.parent.mkdir(parents=True)
        self.csv_path.write_text("existing")
        with self.assertRaisesRegex(CommandError, "already exists"):
            self._seed()

    def test_empty_password_is_rejected(self):
        with self.assertRaisesRegex(CommandError, "non-empty"):
            self._seed(password="")

    def test_refuses_when_load_test_users_already_exist(self):
        User.objects.create_user(username="x", email="nfr02-user-001@example.test")
        with self.assertRaisesRegex(CommandError, "already exists"):
            self._seed()

    def test_database_error_rolls_back_and_removes_files(self):
        from django.db import DatabaseError
        with mock.patch.object(User.objects, "bulk_create", side_effect=DatabaseError):
            with self.assertRaisesRegex(CommandError, "Could not create"):
                self._seed()
        self.assertFalse(self.csv_path.exists())
        self.assertEqual(list(self.csv_path.parent.glob("*.tmp")), [])

    def test_cleanup_removes_users_and_file(self):
        self._seed()
        call_command("seed_load_test_users", confirm_local=True, cleanup=True, stdout=mock.MagicMock())
        self.assertFalse(User.objects.filter(email__endswith="@example.test").exists())
        self.assertFalse(self.csv_path.exists())
