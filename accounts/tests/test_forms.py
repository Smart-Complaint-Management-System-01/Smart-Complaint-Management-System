from unittest.mock import patch

from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from accounts.forms import RegistrationForm
from accounts.models import User


class RegistrationFormTests(TestCase):
    def registration_data(self, **overrides):
        data = {
            "full_name": "Ada Lovelace",
            "email": "ada@example.com",
            "password1": "Sensible-Password-48!",
            "password2": "Sensible-Password-48!",
        }
        data.update(overrides)
        return data

    def test_valid_form_is_accepted(self):
        form = RegistrationForm(data=self.registration_data())

        self.assertTrue(form.is_valid(), form.errors)

    def test_missing_required_fields_are_rejected(self):
        for field in ("full_name", "email", "password1", "password2"):
            with self.subTest(field=field):
                data = self.registration_data()
                data.pop(field)
                form = RegistrationForm(data=data)

                self.assertFalse(form.is_valid())
                self.assertIn(field, form.errors)

    def test_invalid_email_is_rejected(self):
        form = RegistrationForm(data=self.registration_data(email="not-an-email"))

        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_duplicate_email_is_rejected(self):
        User.objects.create_user(
            username="existing-user",
            email="ada@example.com",
            password="Existing-Password-48!",
        )
        form = RegistrationForm(data=self.registration_data())

        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)
        self.assertIn("already exists", str(form.errors["email"]))

    def test_mismatched_passwords_are_rejected(self):
        form = RegistrationForm(
            data=self.registration_data(password2="Different-Password-48!")
        )

        self.assertFalse(form.is_valid())
        self.assertIn("password2", form.errors)

    def test_password_rejected_by_configured_validators_is_rejected(self):
        form = RegistrationForm(
            data=self.registration_data(
                password1="password",
                password2="password",
            )
        )

        self.assertFalse(form.is_valid())
        self.assertIn("password2", form.errors)

    def test_save_stores_a_hashed_password(self):
        raw_password = "Sensible-Password-48!"
        form = RegistrationForm(data=self.registration_data(
            password1=raw_password,
            password2=raw_password,
        ))
        self.assertTrue(form.is_valid(), form.errors)

        user = form.save()

        self.assertNotEqual(user.password, raw_password)
        self.assertTrue(user.check_password(raw_password))

    def test_save_assigns_username_and_splits_full_name(self):
        form = RegistrationForm(data=self.registration_data())
        self.assertTrue(form.is_valid(), form.errors)

        user = form.save()

        self.assertEqual(user.username, "ada@example.com")
        self.assertEqual(user.first_name, "Ada")
        self.assertEqual(user.last_name, "Lovelace")

    def test_long_email_is_truncated_to_username_max_length(self):
        email = f"{'a' * 64}@{'b' * 63}.{'c' * 63}.com"
        form = RegistrationForm(data=self.registration_data(email=email))
        self.assertTrue(form.is_valid(), form.errors)

        user = form.save()

        username_max_length = User._meta.get_field("username").max_length
        self.assertEqual(user.username, email[:username_max_length])
        self.assertLessEqual(len(user.username), username_max_length)

    def test_valid_email_is_normalized_to_username_allowed_characters(self):
        form = RegistrationForm(
            data=self.registration_data(email="o'hara@example.com")
        )
        self.assertTrue(form.is_valid(), form.errors)

        user = form.save()

        self.assertEqual(user.username, "o_hara@example.com")

    def test_collision_after_username_normalization_is_rejected(self):
        User.objects.create_user(
            username="o_hara@example.com",
            email="existing@example.com",
            password="Existing-Password-48!",
        )
        form = RegistrationForm(
            data=self.registration_data(email="o'hara@example.com")
        )

        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)
        self.assertIn("conflicts with an existing username", str(form.errors["email"]))
        self.assertEqual(User.objects.count(), 1)

    def test_public_registration_cannot_grant_privileges(self):
        form = RegistrationForm(
            data=self.registration_data(
                role=User.Role.ADMIN,
                is_staff="on",
                is_superuser="on",
            )
        )
        self.assertTrue(form.is_valid(), form.errors)

        user = form.save()

        self.assertEqual(user.role, User.Role.USER)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_username_collision_does_not_create_partial_account(self):
        User.objects.create_user(
            username="ada@example.com",
            email="other@example.com",
            password="Existing-Password-48!",
        )
        form = RegistrationForm(data=self.registration_data())

        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)
        self.assertIn("conflicts with an existing username", str(form.errors["email"]))

        self.assertEqual(User.objects.count(), 1)
        self.assertFalse(User.objects.filter(email="ada@example.com").exists())


class RegistrationViewTests(TestCase):
    def registration_data(self, **overrides):
        data = {
            "full_name": "Ada Lovelace",
            "email": "view-user@example.com",
            "password1": "Sensible-Password-48!",
            "password2": "Sensible-Password-48!",
        }
        data.update(overrides)
        return data

    def test_get_registration_page_renders_template(self):
        response = self.client.get(reverse("accounts:register"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/register.html")

    def test_valid_post_creates_user_hashes_password_and_redirects(self):
        response = self.client.post(
            reverse("accounts:register"),
            self.registration_data(),
            follow=True,
        )

        self.assertRedirects(response, reverse("accounts:register"))
        user = User.objects.get(email="view-user@example.com")
        self.assertTrue(user.check_password("Sensible-Password-48!"))
        self.assertNotEqual(user.password, "Sensible-Password-48!")
        self.assertContains(response, "Your account has been created successfully.")

    def test_invalid_post_redisplays_errors_and_non_password_values(self):
        password1 = "Invalid-Password-One-48!"
        password2 = "Invalid-Password-Two-48!"
        response = self.client.post(
            reverse("accounts:register"),
            self.registration_data(
                full_name="Grace Hopper",
                email="not-an-email",
                password1=password1,
                password2=password2,
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/register.html")
        self.assertIn("email", response.context["form"].errors)
        self.assertIn("password2", response.context["form"].errors)
        self.assertContains(response, 'value="Grace Hopper"')
        self.assertContains(response, 'value="not-an-email"')
        self.assertNotContains(response, password1)
        self.assertNotContains(response, password2)

    def test_integrity_error_rolls_back_user_creation_and_shows_form_error(self):
        def create_user_then_raise_integrity_error(form):
            email = form.cleaned_data["email"]
            User.objects.create_user(
                username=form._username_from_email(email),
                email=email,
                password=form.cleaned_data["password1"],
            )
            raise IntegrityError("simulated concurrent uniqueness conflict")

        with patch(
            "accounts.views.RegistrationForm.save",
            autospec=True,
            side_effect=create_user_then_raise_integrity_error,
        ) as save_mock:
            response = self.client.post(
                reverse("accounts:register"),
                self.registration_data(),
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("email", response.context["form"].errors)
        self.assertIn("already exists", str(response.context["form"].errors["email"]))
        self.assertFalse(User.objects.filter(email="view-user@example.com").exists())
        save_mock.assert_called_once()
