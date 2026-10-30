from django.contrib import admin

from .models import Complaint, ComplaintHistory, Department, Notification


class ComplaintHistoryInline(admin.TabularInline):
    model = ComplaintHistory
    extra = 0
    can_delete = False
    readonly_fields = ("previous_status", "new_status", "updated_by", "update_details", "created_at")


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ("complaint_id", "title", "user", "category", "status", "created_at")
    list_filter = ("status", "category")
    search_fields = ("complaint_id", "title", "user__email")
    readonly_fields = ("complaint_id",)
    inlines = [ComplaintHistoryInline]


admin.site.register(Department)
admin.site.register(Notification)
