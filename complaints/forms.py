from django import forms

from .models import Complaint


class ComplaintForm(forms.ModelForm):
    class Meta:
        model = Complaint
        fields = ("category", "title", "description")
        widgets = {
            "title": forms.TextInput(attrs={"maxlength": 150}),
            "description": forms.Textarea(attrs={"rows": 6}),
        }
