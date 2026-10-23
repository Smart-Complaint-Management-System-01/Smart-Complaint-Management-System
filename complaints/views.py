from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.decorators import role_required
from accounts.models import User

from .forms import ComplaintForm


@role_required(User.Role.USER)
def new_complaint(request):
    if request.method == "POST":
        form = ComplaintForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                complaint = form.save(commit=False)
                complaint.user = request.user
                complaint.save()
            return redirect(
                reverse("complaints:submission_confirmation", args=[complaint.complaint_id])
            )
    else:
        form = ComplaintForm()

    return render(request, "complaints/new.html", {"form": form})


@role_required(User.Role.USER)
def submission_confirmation(request, complaint_id):
    complaint = get_object_or_404(
        request.user.complaints, complaint_id=complaint_id
    )
    return render(
        request,
        "complaints/new.html",
        {"form": ComplaintForm(), "complaint": complaint},
    )
