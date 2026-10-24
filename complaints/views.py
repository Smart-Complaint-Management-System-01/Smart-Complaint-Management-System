
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import Complaint


@login_required
def my_complaints(request):
    complaints = Complaint.objects.filter(user=request.user)

    return render(
        request,
        "complaints/my_complaints.html",
        {"complaints": complaints},
    )
