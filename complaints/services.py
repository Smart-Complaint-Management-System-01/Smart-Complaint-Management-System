from django.db import transaction

from .models import Complaint, ComplaintHistory

S = Complaint.Status

# Allowed workflow (Sprint 2): branching transitions, values are sets
NEXT_STATUS = {
    S.SUBMITTED:    {S.UNDER_REVIEW, S.REJECTED},
    S.UNDER_REVIEW: {S.ASSIGNED,     S.REJECTED},
    S.ASSIGNED:     {S.IN_PROGRESS},
    S.IN_PROGRESS:  {S.RESOLVED},
    S.RESOLVED:     {S.CLOSED},
    S.REJECTED:     {S.CLOSED},
}


class InvalidTransition(Exception):
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
