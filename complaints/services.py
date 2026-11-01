
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from .models import Complaint, ComplaintHistory

S = Complaint.Status

# Allowed workflow (Sprint 2): branching transitions, values are sets
NEXT_STATUS = {
    S.SUBMITTED: {S.UNDER_REVIEW, S.REJECTED},
    S.UNDER_REVIEW: {S.ASSIGNED, S.REJECTED},
    S.ASSIGNED: {S.IN_PROGRESS},
    S.IN_PROGRESS: {S.RESOLVED},
    S.RESOLVED: {S.CLOSED},
    S.REJECTED: {S.CLOSED},
}


class InvalidTransition(Exception):
    pass


class InvalidAssignment(Exception):
    pass


def record_history(complaint, previous_status, new_status, actor=None, details=""):
    """Write one ComplaintHistory row (SAD 3.9 non-repudiation)."""
    return ComplaintHistory.objects.create(
        complaint=complaint,
        previous_status=previous_status or "",
        new_status=new_status,
        updated_by=actor,
        update_details=details,
    )


def record_initial_status(complaint, actor=None, details="Complaint submitted"):
    """Record the SUBMITTED status when a complaint is first created (idempotent)."""
    ComplaintHistory.objects.get_or_create(
        complaint=complaint,
        previous_status="",
        new_status=Complaint.Status.SUBMITTED,
        defaults={"updated_by": actor, "update_details": details},
    )


def change_status(complaint, new_status, actor=None, details=""):
    if new_status == S.RESOLVED:
        raise InvalidTransition("Record the resolution details to resolve a complaint.")

    if new_status not in NEXT_STATUS.get(complaint.status, set()):
        raise InvalidTransition(
            f"Cannot move a complaint from '{complaint.get_status_display()}' to '{new_status}'."
        )

    previous = complaint.status

    with transaction.atomic():
        complaint.status = new_status
        complaint.save(update_fields=["status", "updated_at"])
        record_history(complaint, previous, new_status, actor, details)

    return complaint


def resolve_complaint(complaint, resolution_text, actor=None):
    resolution_text = (resolution_text or "").strip()

    if not resolution_text:
        raise ValueError("Please enter the resolution details.")

    if complaint.status != S.IN_PROGRESS:
        raise InvalidTransition("Only complaints that are In Progress can be resolved.")

    previous = complaint.status

    with transaction.atomic():
        complaint.status = S.RESOLVED
        complaint.resolution_details = resolution_text
        complaint.resolved_at = timezone.now()

        complaint.save(
            update_fields=[
                "status",
                "resolution_details",
                "resolved_at",
                "updated_at",
            ]
        )

        record_history(
            complaint,
            previous,
            S.RESOLVED,
            actor,
            "Resolved: " + resolution_text,
        )

    return complaint


# FR-09: Complaint assignment

def assign_complaint(complaint, assigned_to=None, department=None, actor=None):
    """
    Assign a complaint to an administrator and/or department.

    First assignment moves UNDER_REVIEW to ASSIGNED.
    Reassignment preserves ASSIGNED or IN_PROGRESS status.
    Every assignment is recorded in complaint history.
    """

    if assigned_to is None and department is None:
        raise InvalidAssignment(
            "Select an administrator or a department."
        )

    if assigned_to is not None:
        if assigned_to.role != User.Role.ADMIN or not assigned_to.is_active:
            raise InvalidAssignment(
                "The selected assignee must be an active administrator."
            )

    allowed_statuses = {
        S.UNDER_REVIEW,
        S.ASSIGNED,
        S.IN_PROGRESS,
    }

    if complaint.status not in allowed_statuses:
        raise InvalidAssignment(
            "This complaint cannot be assigned in its current status."
        )

    with transaction.atomic():
        previous_status = complaint.status

        complaint.assigned_to = assigned_to
        complaint.assigned_department = department

        if previous_status == S.UNDER_REVIEW:
            complaint.status = S.ASSIGNED

        complaint.save(
            update_fields=[
                "assigned_to",
                "assigned_department",
                "status",
                "updated_at",
            ]
        )

        assignee_name = (
            assigned_to.get_full_name() or assigned_to.username
            if assigned_to
            else "None"
        )

        department_name = department.name if department else "None"

        details = (
            "Assignment updated: Administrator = "
            + assignee_name
            + ", Department = "
            + department_name
        )

        record_history(
            complaint,
            previous_status,
            complaint.status,
            actor=actor,
            details=details,
        )

    return complaint
