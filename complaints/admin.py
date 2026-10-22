from django.contrib import admin

from .models import Complaint


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ("complaint_id", "title", "user", "category", "status", "created_at")
    list_filter = ("status", "category")
    search_fields = ("complaint_id", "title", "user__email")
    readonly_fields = ("complaint_id",)