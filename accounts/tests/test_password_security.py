from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import identify_hasher, is_password_usable
from django.db import connection
from django.test import TestCase
from django.urls import reverse

User = get_user_model()
RAW = "Sensible-Password-48!"


class PasswordProtectionTests(TestCase):
    def register(self, email="pw@example.com"):
        self.client.post(reverse("accounts:register"), {
            "full_name": "Pat Word", "email": email, "password1": RAW, "password2": RAW,
        })
        return User.objects.get(email=email)

    def test_registration_stores_pbkdf2_hash(self):
        user = self.register()
        self.assertTrue(user.password.startswith("pbkdf2_sha256$"))
        self.assertNotIn(RAW, user.password)
        self.assertTrue(is_password_usable(user.password))
        self.assertEqual(identify_hasher(user.password).algorithm, "pbkdf2_sha256")

    def test_raw_database_row_contains_no_plaintext(self):
        self.register()
        with connection.cursor() as cursor:
            cursor.execute("SELECT password FROM accounts_user WHERE email = %s", ["pw@example.com"])
            stored = cursor.fetchone()[0]
        self.assertNotEqual(stored, RAW)
        self.assertNotIn(RAW, stored)

    def test_same_password_gives_different_hashes_because_of_salt(self):
        a = self.register("a@example.com")
        b = self.register("b@example.com")
        self.assertNotEqual(a.password, b.password)

    def test_superuser_password_is_hashed(self):
        su = User.objects.create_superuser(username="root", email="root@x.com", password=RAW)
        self.assertNotEqual(su.password, RAW)
        self.assertTrue(su.check_password(RAW))

    def test_plaintext_and_weak_hashers_not_configured(self):
        names = " ".join(settings.PASSWORD_HASHERS).lower()
        self.assertNotIn("unsalted", names)
        self.assertNotIn("md5", names)
        self.assertTrue(settings.PASSWORD_HASHERS[0].endswith("PBKDF2PasswordHasher"))

    def test_password_is_never_echoed_in_failed_login_response(self):
        User.objects.create_user(username="x@x.com", email="x@x.com", password=RAW)
        response = self.client.post(reverse("accounts:login"), {"email": "x@x.com", "password": "Wrong-Pass-123!"})
        self.assertNotContains(response, "Wrong-Pass-123!")
    