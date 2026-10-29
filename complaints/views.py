
import logging
import uuid

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import DatabaseError, IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.decorators import admin_required, role_required
from accounts.models import User

from .forms import ComplaintForm
from .models import Complaint
from .services import NEXT_STATUS, InvalidTransition, change_status

logger = logging.getLogger(__name__)


def _issue_form_token(request):
    request.session["complaint_form_token"] = uuid.uuid4().hex


# FR-04, NFR-04 and NFR-06: Complaint submission, recovery and validation feedback
@role_required(User.Role.USER)
def new_complaint(request):
    if request.method == "POST":
        token = request.POST.get("form_token")
        if not token or token != request.session.get("complaint_form_token"):
            messages.warning(request, "This complaint was already submitted.")
            return redirect("complaints:my_list")

        form = ComplaintForm(request.POST)

        if form.is_valid():
            try:
                with transaction.atomic():
                    complaint = form.save(commit=False)
                    complaint.user = request.user
                    complaint.submission_token = token
                    complaint.save()
            except IntegrityError:
                complaint = Complaint.objects.filter(
                    user=request.user,
                    submission_token=token,
                ).first()
                if complaint is None:
                    logger.exception("Complaint submission failed")
                    messages.error(
                        request,
                        "We couldn't save your complaint. Please try again.",
                    )
                    return render(
                        request, "complaints/new.html", {"form": form}, status=500
                    )

                request.session.pop("complaint_form_token", None)
                return redirect(
                    reverse(
                        "complaints:submission_confirmation",
                        args=[complaint.complaint_id],
                    )
                )
            except DatabaseError:
                logger.exception("Complaint submission failed")
                messages.error(
                    request,
                    "We couldn't save your complaint. Please try again.",
                )
                return render(
                    request, "complaints/new.html", {"form": form}, status=500
                )

            request.session.pop("complaint_form_token", None)
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
        _issue_form_token(request)

    return render(request, "complaints/new.html", {"form": form})


# FR-04: Submission confirmation
@role_required(User.Role.USER)
def submission_confirmation(request, complaint_id):
    complaint = get_object_or_404(
        request.user.complaints,
        complaint_id=complaint_id,
    )
    _issue_form_token(request)
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


# FR-08: Admin complaint management
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
            "next_status": NEXT_STATUS.get(complaint.status),
        },
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
        messages.success(
            request,
            "Status updated to " + complaint.get_status_display() + ".",
        )

    return redirect("complaints:admin_detail", pk=pk)
