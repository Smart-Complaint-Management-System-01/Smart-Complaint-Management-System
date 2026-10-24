from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import admin_required

from .models import Complaint
from .services import NEXT_STATUS, InvalidTransition, change_status
from django.contrib.auth.decorators import login_required

from .forms import ComplaintForm

# NFR-06 - Validation Feedback
@login_required
def new_complaint(request):
    if request.method == "POST":
        form = ComplaintForm(request.POST)

        if form.is_valid():
            complaint = form.save(commit=False)
            complaint.user = request.user
            complaint.save()

            messages.success(
                request,
                "Your complaint was submitted successfully."
            )
            return redirect("complaints:my_list")
    else:
        form = ComplaintForm()

    return render(
        request,
        "complaints/new.html",
        {"form": form},
    )


# ---- FR-08: Admin complaint management (Rakshita) ----
@admin_required
def admin_list(request):
    queryset = Complaint.objects.select_related("user")
    page = Paginator(queryset, 10).get_page(request.GET.get("page"))
    return render(request, "complaints/admin_list.html", {"page": page})


@admin_required
def admin_detail(request, pk):
    complaint = get_object_or_404(Complaint.objects.select_related("user"), pk=pk)
    return render(
        request,
        "complaints/admin_detail.html",
        {"complaint": complaint, "next_status": NEXT_STATUS.get(complaint.status)},
    )


@admin_required
@require_POST
def admin_update_status(request, pk):
    complaint = get_object_or_404(Complaint, pk=pk)
    try:
        change_status(complaint, request.POST.get("status"))
    except InvalidTransition as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"Status updated to {complaint.get_status_display()}.")
    return redirect("complaints:admin_detail", pk=pk)