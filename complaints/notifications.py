from .models import Complaint, Notification


def notify_status_change(complaint, new_status):
    """Create an in-app notification for the complaint owner on a real status change."""
    display = dict(Complaint.Status.choices).get(new_status, new_status)
    Notification.objects.create(
        user=complaint.user,
        complaint=complaint,
        message=f"Your complaint {complaint.complaint_id} is now {display}.",
    )
