from django.db import transaction

from .models import Complaint, ComplaintHistory

S = Complaint.Status

# Allowed workflow (SAD 4.1): one step forward at a time
NEXT_STATUS = {
    S.SUBMITTED: S.UNDER_REVIEW,
    S.UNDER_REVIEW: S.ASSIGNED,
    S.ASSIGNED: S.IN_PROGRESS,
    S.IN_PROGRESS: S.RESOLVED,
}


class InvalidTransition(Exception):
    pass


def record_initial_status(complaint, actor=None):
    """Record the SUBMITTED status when a complaint is first created."""
    ComplaintHistory.objects.get_or_create(
        complaint=complaint,
        previous_status=None,
        new_status=Complaint.Status.SUBMITTED,
        defaults={"changed_by": actor},
    )


def change_status(complaint, new_status, actor=None):
    if NEXT_STATUS.get(complaint.status) != new_status:
        raise InvalidTransition(
            f"Cannot move a complaint from '{complaint.get_status_display()}' to '{new_status}'."
        )
    previous = complaint.status
    with transaction.atomic():
        complaint.status = new_status
        complaint.save(update_fields=["status", "updated_at"])
        ComplaintHistory.objects.create(
            complaint=complaint,
            previous_status=previous,
            new_status=new_status,
            changed_by=actor,
        )
    return complaint
