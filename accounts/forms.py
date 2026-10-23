from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError

from .models import User


class RegistrationForm(UserCreationForm):
    full_name = forms.CharField(max_length=100)

    class Meta:
        model = User
        fields = ("full_name", "email")

    def _username_from_email(self, email):
        username_field = User._meta.get_field("username")
        username_validator = next(
            validator
            for validator in username_field.validators
            if isinstance(validator, UnicodeUsernameValidator)
        )
        username = "".join(
            character if username_validator.regex.fullmatch(character) else "_"
            for character in email
        )
        return username[: username_field.max_length]

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email address already exists.")
        username = self._username_from_email(email)
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError(
                "This email address conflicts with an existing username."
            )
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self._username_from_email(user.email)
        name_parts = self.cleaned_data["full_name"].split(maxsplit=1)
        user.first_name = name_parts[0]
        user.last_name = name_parts[1] if len(name_parts) > 1 else ""
        if commit:
            user.save()
            self.save_m2m()
        return user
