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

from .forms import ComplaintForm, UpdateNoteForm
from .models import Complaint
from .services import (
    NEXT_STATUS,
    InvalidTransition,
    add_update,
    change_status,
    record_history,
)
from .search import ComplaintFilterForm, filter_complaints

logger = logging.getLogger(__name__)


def _issue_form_token(request):
    """NFR-04: one-time token that stops the same submission being saved twice."""
    request.session["complaint_form_token"] = uuid.uuid4().hex


# FR-04, NFR-04 and NFR-06: Complaint submission, error recovery and validation feedback
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

                    record_history(
                        complaint,
                        "",
                        Complaint.Status.SUBMITTED,
                        actor=request.user,
                        details="Complaint submitted",
                    )

            except IntegrityError:
                # Same token already saved (double click / replay): reuse that complaint.
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
                        request,
                        "complaints/new.html",
                        {"form": form},
                        status=500,
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
                    request,
                    "complaints/new.html",
                    {"form": form},
                    status=500,
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


# FR-05 and NFR-01: View my complaints (paginated)
@role_required(User.Role.USER)
def my_complaints(request):
    queryset = Complaint.objects.filter(user=request.user).order_by("-created_at")
    page = Paginator(queryset, 10).get_page(request.GET.get("page"))

    return render(
        request,
        "complaints/my_complaints.html",
        {"complaints": page, "page": page},
    )


# FR-06: User complaint detail
@role_required(User.Role.USER)
def complaint_detail(request, complaint_id):
    complaint = get_object_or_404(
        request.user.complaints,
        complaint_id=complaint_id,
    )

    entries = complaint.history.select_related("updated_by").all()

    return render(
        request,
        "complaints/complaint_detail.html",
        {"complaint": complaint, "entries": entries},
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


# FR-08 / FR-11: Admin list with search and filtering
@admin_required
def admin_list(request):
    form = ComplaintFilterForm(request.GET or None)

    queryset = Complaint.objects.select_related(
        "user",
        "assigned_to",
        "assigned_department",
    )

    if form.is_valid():
        queryset = filter_complaints(queryset, form.cleaned_data)

    page = Paginator(queryset, 10).get_page(request.GET.get("page"))

    params = request.GET.copy()
    params.pop("page", None)

    return render(
        request,
        "complaints/admin_list.html",
        {
            "page": page,
            "form": form,
            "querystring": params.urlencode(),
        },
    )


@admin_required
def admin_detail(request, pk):
    complaint = get_object_or_404(
        Complaint.objects.select_related("user"),
        pk=pk,
    )

    from .models import Department

    return render(
        request,
        "complaints/admin_detail.html",
        {
            "complaint": complaint,
            "next_status": next(
                iter(sorted(NEXT_STATUS.get(complaint.status, set()))),
                None,
            ),
            "next_statuses": sorted(
                NEXT_STATUS.get(complaint.status, set())
            ),
            "history": complaint.history.select_related("updated_by"),
            "departments": Department.objects.all(),
            "admin_users": User.objects.filter(
                role=User.Role.ADMIN,
                is_active=True,
            ),
        },
    )


@admin_required
@require_POST
def admin_update_status(request, pk):
    complaint = get_object_or_404(Complaint, pk=pk)

    try:
        change_status(
            complaint,
            request.POST.get("status"),
            actor=request.user,
        )

    except InvalidTransition as exc:
        messages.error(request, str(exc))

    else:
        messages.success(
            request,
            "Status updated to " + complaint.get_status_display() + ".",
        )

    return redirect("complaints:admin_detail", pk=pk)


# FR-07: Admin adds an update to a complaint
@admin_required
@require_POST
def admin_add_update(request, pk):
    complaint = get_object_or_404(Complaint, pk=pk)
    form = UpdateNoteForm(request.POST)

    if not form.is_valid():
        for error in form.errors["note"]:
            messages.error(request, error)

    else:
        try:
            add_update(
                complaint,
                request.user,
                form.cleaned_data["note"],
            )

        except (InvalidTransition, ValueError) as exc:
            messages.error(request, str(exc))

        else:
            messages.success(request, "Update added.")

    return redirect("complaints:admin_detail", pk=pk)

# FR-07: User adds additional information to their own complaint
@role_required(User.Role.USER)
@require_POST
def add_info(request, complaint_id):
    complaint = get_object_or_404(
        request.user.complaints,
        complaint_id=complaint_id,
    )

    form = UpdateNoteForm(request.POST)

    if not form.is_valid():
        for error in form.errors["note"]:
            messages.error(request, error)

    else:
        try:
            add_update(
                complaint,
                request.user,
                form.cleaned_data["note"],
            )

        except (InvalidTransition, ValueError) as exc:
            messages.error(request, str(exc))

        else:
            messages.success(
                request,
                "Your information was added to the complaint.",
            )

    return redirect("complaints:complaint_detail", complaint_id=complaint_id)