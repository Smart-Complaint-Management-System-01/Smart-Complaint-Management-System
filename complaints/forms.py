from django import forms

from accounts.models import User
from .models import Complaint, Department


class ComplaintForm(forms.ModelForm):
    category = forms.ChoiceField(
        choices=Complaint.Category.choices,
        required=True,
        error_messages={
            "required": "Please select a complaint category.",
            "invalid_choice": "Please select a valid complaint category.",
        },
    )

    title = forms.CharField(
        max_length=150,
        strip=False,
        required=True,
        error_messages={
            "required": "Please enter a complaint title.",
            "max_length": "The complaint title must be 150 characters or fewer.",
        },
        widget=forms.TextInput(attrs={"maxlength": 150}),
    )

    description = forms.CharField(
        strip=False,
        required=True,
        error_messages={
            "required": "Please enter a description of your complaint.",
        },
        widget=forms.Textarea(attrs={"rows": 6}),
    )

    class Meta:
        model = Complaint
        fields = ("category", "title", "description")

    def clean_title(self):
        title = self.cleaned_data["title"].strip()

        if not title:
            raise forms.ValidationError("Please enter a complaint title.")

        return title

    def clean_description(self):
        description = self.cleaned_data["description"].strip()

        if not description:
            raise forms.ValidationError(
                "Please enter a description of your complaint."
            )

        return description


class AssignmentForm(forms.Form):
    assigned_to = forms.ModelChoiceField(
        queryset=User.objects.filter(
            role=User.Role.ADMIN,
            is_active=True,
        ),
        required=False,
        empty_label="Select an administrator",
    )

    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        required=False,
        empty_label="Select a department",
    )

    def clean(self):
        cleaned_data = super().clean()

        assigned_to = cleaned_data.get("assigned_to")
        department = cleaned_data.get("department")

        if not assigned_to and not department:
            raise forms.ValidationError(
                "Select an administrator, a department, or both."
            )

        return cleaned_data