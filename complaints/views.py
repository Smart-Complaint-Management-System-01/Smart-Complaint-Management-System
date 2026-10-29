
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.decorators import admin_required, role_required
from accounts.models import User

from .forms import ComplaintForm
from .models import Complaint, ComplaintHistory
from .services import NEXT_STATUS, InvalidTransition, change_status, record_initial_status


# FR-04 and NFR-06: Complaint submission and validation feedback
@role_required(User.Role.USER)
def new_complaint(request):
    if request.method == "POST":
        form = ComplaintForm(request.POST)

        if form.is_valid():
            with transaction.atomic():
                complaint = form.save(commit=False)
                complaint.user = request.user
                complaint.save()
                record_initial_status(complaint, actor=request.user)

            messages.success(
                request,
                "Your complaint was submitted successfully.",
            )

            return redirect(
                reverse(
                    "complaints:submission_confirmation",
                    args=[complaint.complaint_id],
                )
            )
    else:
        form = ComplaintForm()

    return render(request, "complaints/new.html", {"form": form})


# FR-04: Submission confirmation
@role_required(User.Role.USER)
def submission_confirmation(request, complaint_id):
    complaint = get_object_or_404(
        request.user.complaints,
        complaint_id=complaint_id,
    )
    return render(
        request,
        "complaints/new.html",
        {"form": ComplaintForm(), "complaint": complaint},
    )


# FR-05: View my complaints
@role_required(User.Role.USER)
def my_complaints(request):
    complaints = Complaint.objects.filter(user=request.user)
    return render(
        request,
        "complaints/my_complaints.html",
        {"complaints": complaints},
    )


# FR-06: User complaint history
@role_required(User.Role.USER)
def complaint_history(request, complaint_id):
    complaint = get_object_or_404(
        request.user.complaints,
        complaint_id=complaint_id,
    )
    entries = complaint.history.select_related("updated_by").all()
    return render(
        request,
        "complaints/history.html",
        {"complaint": complaint, "entries": entries},
    )


# FR-06: Admin complaint history
@admin_required
def admin_complaint_history(request, pk):
    complaint = get_object_or_404(
        Complaint.objects.select_related("user"),
        pk=pk,
    )
    entries = complaint.history.select_related("updated_by").all()
    return render(
        request,
        "complaints/admin_history.html",
        {"complaint": complaint, "entries": entries},
    )

@admin_required
def admin_list(request):
    queryset = Complaint.objects.select_related("user")
    page = Paginator(queryset, 10).get_page(request.GET.get("page"))
    return render(request, "complaints/admin_list.html", {"page": page})


@admin_required
def admin_detail(request, pk):
    complaint = get_object_or_404(
        Complaint.objects.select_related("user"),
        pk=pk,
    )
    return render(
        request,
        "complaints/admin_detail.html",
        {
            "complaint": complaint,
            "next_statuses": sorted(NEXT_STATUS.get(complaint.status, set())),
        },
    )


@admin_required
@require_POST
def admin_update_status(request, pk):
    complaint = get_object_or_404(Complaint, pk=pk)

    try:
        change_status(complaint, request.POST.get("status"), actor=request.user)
    except InvalidTransition as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request,
            "Status updated to " + complaint.get_status_display() + ".",
        )

    return redirect("complaints:admin_detail", pk=pk)
