from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        USER = "USER", "Complainant / User"
        ADMIN = "ADMIN", "Administrator"

    email = models.EmailField("email address", unique=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.USER)
    @property
    def is_admin_role(self):
        return self.role == self.Role.ADMIN

    def save(self, *args, **kwargs):
        if self.is_superuser:  # createsuperuser accounts are always administrators
            self.role = self.Role.ADMIN
        super().save(*args, **kwargs)