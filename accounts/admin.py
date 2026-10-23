from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("email", "first_name", "role", "is_active")
    list_filter = ("role", "is_active")
    search_fields = ("email", "first_name")
    fieldsets = UserAdmin.fieldsets + (("Role", {"fields": ("role",)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("Email & role", {"fields": ("email", "role")}),)