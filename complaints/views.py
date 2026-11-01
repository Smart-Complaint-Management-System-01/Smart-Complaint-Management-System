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

from .forms import AssignmentForm, ComplaintForm, UpdateNoteForm
from .models import Complaint, Department
from .services import (
    NEXT_STATUS,
    InvalidAssignment,
    InvalidTransition,
    add_update,
    assign_complaint,
    change_status,
    record_history,
    resolve_complaint,
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
                # Same token already saved: reuse that complaint.
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