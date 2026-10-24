from .models import Complaint

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


def change_status(complaint, new_status):
    if NEXT_STATUS.get(complaint.status) != new_status:
        raise InvalidTransition(
            f"Cannot move a complaint from '{complaint.get_status_display()}' to '{new_status}'."
        )
    complaint.status = new_status
    complaint.save(update_fields=["status", "updated_at"])
    return complaint