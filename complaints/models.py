from django.conf import settings
from django.db import models, transaction


class Complaint(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "SUBMITTED", "Submitted"
        UNDER_REVIEW = "UNDER_REVIEW", "Under Review"
        ASSIGNED = "ASSIGNED", "Assigned"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        RESOLVED = "RESOLVED", "Resolved"
        REJECTED = "REJECTED", "Rejected"
        CLOSED = "CLOSED", "Closed"

    class Category(models.TextChoices):  # final list still open in SAD 4.6
        ACADEMIC = "ACADEMIC", "Academic"
        HOSTEL = "HOSTEL", "Hostel"
        INFRASTRUCTURE = "INFRASTRUCTURE", "Infrastructure"
        TRANSPORT = "TRANSPORT", "Transport"
        ADMINISTRATIVE = "ADMINISTRATIVE", "Administrative"
        OTHER = "OTHER", "Other"

    # null=True so several rows can briefly have no ID before it is generated
    complaint_id = models.CharField(
        max_length=20, unique=True, null=True, blank=True, editable=False
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="complaints"
    )
    category = models.CharField(max_length=20, choices=Category.choices)
    title = models.CharField(max_length=150)
    description = models.TextField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.SUBMITTED, db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.complaint_id or 'NEW'} - {self.title}"

    def save(self, *args, **kwargs):
        # Insert + ID generation happen atomically: no half-saved complaints (NFR-04)
        with transaction.atomic():
            super().save(*args, **kwargs)
            if not self.complaint_id:
                self.complaint_id = f"CMP-{self.pk:06d}"
                super().save(update_fields=["complaint_id"])


class ComplaintHistory(models.Model):
    complaint = models.ForeignKey(
        Complaint, on_delete=models.CASCADE, related_name="history"
    )
    previous_status = models.CharField(
        max_length=20, choices=Complaint.Status.choices, null=True, blank=True
    )
    new_status = models.CharField(max_length=20, choices=Complaint.Status.choices)
    updated_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_history_entries",
    )
    update_details = models.TextField(blank=True)

    class Meta:
        ordering = ["updated_at"]
        verbose_name_plural = "complaint history"

    def __str__(self):
        prev = self.previous_status or "—"
        return f"{self.complaint.complaint_id}: {prev} → {self.new_status}"