from datetime import datetime, time

from django import forms
from django.utils import timezone

from .models import Complaint


class ComplaintFilterForm(forms.Form):
    complaint_id = forms.CharField(required=False, max_length=20, label="Complaint ID")
    category = forms.ChoiceField(
        required=False, choices=[("", "All categories")] + Complaint.Category.choices
    )
    status = forms.ChoiceField(
        required=False, choices=[("", "All statuses")] + Complaint.Status.choices
    )
    from_date = forms.DateField(required=False, label="From", widget=forms.DateInput(attrs={"type": "date"}))
    to_date = forms.DateField(required=False, label="To", widget=forms.DateInput(attrs={"type": "date"}))

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("from_date"), cleaned.get("to_date")
        if start and end and start > end:
            raise forms.ValidationError("The 'From' date cannot be after the 'To' date.")
        return cleaned


def filter_complaints(queryset, data):
    complaint_id = (data.get("complaint_id") or "").strip()
    if complaint_id:
        queryset = queryset.filter(complaint_id__icontains=complaint_id)
    if data.get("category"):
        queryset = queryset.filter(category=data["category"])
    if data.get("status"):
        queryset = queryset.filter(status=data["status"])
    # Range filters on the datetime column, not __date: MySQL's __date needs timezone tables loaded.
    if data.get("from_date"):
        start = timezone.make_aware(datetime.combine(data["from_date"], time.min))
        queryset = queryset.filter(created_at__gte=start)
    if data.get("to_date"):
        end = timezone.make_aware(datetime.combine(data["to_date"], time.max))
        queryset = queryset.filter(created_at__lte=end)
    return queryset