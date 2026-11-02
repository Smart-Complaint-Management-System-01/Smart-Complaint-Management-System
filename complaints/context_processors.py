from .models import Notification


def notification_count(request):
    if request.user.is_authenticated and request.user.role == "USER":
        count = Notification.objects.filter(user=request.user, is_read=False).count()
    else:
        count = 0
    return {"unread_notification_count": count}
