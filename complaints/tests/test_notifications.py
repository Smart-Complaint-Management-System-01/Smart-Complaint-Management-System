from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from complaints.models import Complaint, Notification
from complaints.services import change_status, record_history, resolve_complaint

User = get_user_model()
S = Complaint.Status


def make_user(email, role=User.Role.USER):
    return User.objects.create_user(username=email, email=email, password=None, role=role)


def make_complaint(user, status=S.SUBMITTED):
    return Complaint.objects.create(
        user=user,
        category=Complaint.Category.OTHER,
        title="Test complaint",
        description="A description long enough.",
        status=status,
    )


# ---------------------------------------------------------------------------
# Service-level: notification creation rules
# ---------------------------------------------------------------------------

class NotifyOnStatusChangeTests(TestCase):
    """record_history() creates notifications only on real transitions."""

    @classmethod
    def setUpTestData(cls):
        cls.user = make_user("owner@notif.com")
        cls.admin = make_user("admin@notif.com", role=User.Role.ADMIN)

    def setUp(self):
        self.complaint = make_complaint(self.user)

    def test_real_transition_creates_notification(self):
        record_history(self.complaint, S.SUBMITTED, S.UNDER_REVIEW, actor=self.admin)
        self.assertEqual(Notification.objects.filter(complaint=self.complaint).count(), 1)

    def test_notification_recipient_is_complaint_owner(self):
        record_history(self.complaint, S.SUBMITTED, S.UNDER_REVIEW, actor=self.admin)
        n = Notification.objects.get(complaint=self.complaint)
        self.assertEqual(n.user, self.user)

    def test_notification_message_contains_new_status(self):
        record_history(self.complaint, S.SUBMITTED, S.UNDER_REVIEW, actor=self.admin)
        n = Notification.objects.get(complaint=self.complaint)
        self.assertIn("Under Review", n.message)

    def test_notification_message_contains_complaint_id(self):
        record_history(self.complaint, S.SUBMITTED, S.UNDER_REVIEW, actor=self.admin)
        n = Notification.objects.get(complaint=self.complaint)
        self.assertIn(self.complaint.complaint_id, n.message)

    def test_notification_message_exact_format(self):
        record_history(self.complaint, S.SUBMITTED, S.UNDER_REVIEW, actor=self.admin)
        n = Notification.objects.get(complaint=self.complaint)
        self.assertEqual(
            n.message,
            f"Your complaint {self.complaint.complaint_id} is now Under Review.",
        )

    def test_initial_submission_creates_no_notification(self):
        """previous_status='' means initial entry — no notification."""
        record_history(self.complaint, "", S.SUBMITTED, actor=self.user)
        self.assertEqual(Notification.objects.filter(complaint=self.complaint).count(), 0)

    def test_plain_note_same_status_creates_no_notification(self):
        """previous_status == new_status (plain note) — no notification."""
        record_history(self.complaint, S.SUBMITTED, S.SUBMITTED, actor=self.admin, details="Note")
        self.assertEqual(Notification.objects.filter(complaint=self.complaint).count(), 0)

    def test_notification_is_unread_by_default(self):
        record_history(self.complaint, S.SUBMITTED, S.UNDER_REVIEW, actor=self.admin)
        n = Notification.objects.get(complaint=self.complaint)
        self.assertFalse(n.is_read)

    def test_change_status_creates_notification(self):
        self.complaint.status = S.SUBMITTED
        self.complaint.save(update_fields=["status", "updated_at"])
        change_status(self.complaint, S.UNDER_REVIEW, actor=self.admin)
        self.assertEqual(Notification.objects.filter(complaint=self.complaint).count(), 1)

    def test_resolve_complaint_creates_notification(self):
        self.complaint.status = S.IN_PROGRESS
        self.complaint.save(update_fields=["status", "updated_at"])
        resolve_complaint(self.complaint, "Fixed.", actor=self.admin)
        self.assertEqual(Notification.objects.filter(complaint=self.complaint).count(), 1)

    def test_resolve_notification_recipient_is_owner(self):
        self.complaint.status = S.IN_PROGRESS
        self.complaint.save(update_fields=["status", "updated_at"])
        resolve_complaint(self.complaint, "Fixed.", actor=self.admin)
        n = Notification.objects.get(complaint=self.complaint)
        self.assertEqual(n.user, self.user)

    def test_multiple_transitions_create_multiple_notifications(self):
        self.complaint.status = S.SUBMITTED
        self.complaint.save(update_fields=["status", "updated_at"])
        change_status(self.complaint, S.UNDER_REVIEW, actor=self.admin)
        self.complaint.refresh_from_db()
        change_status(self.complaint, S.ASSIGNED, actor=self.admin)
        self.assertEqual(Notification.objects.filter(complaint=self.complaint).count(), 2)

    def test_notifications_for_different_complaints_are_independent(self):
        other_user = make_user("other@notif.com")
        other_complaint = make_complaint(other_user)
        record_history(self.complaint, S.SUBMITTED, S.UNDER_REVIEW, actor=self.admin)
        record_history(other_complaint, S.SUBMITTED, S.UNDER_REVIEW, actor=self.admin)
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 1)
        self.assertEqual(Notification.objects.filter(user=other_user).count(), 1)


# ---------------------------------------------------------------------------
# View: /notifications/
# ---------------------------------------------------------------------------

class NotificationsViewTests(TestCase):
    """Integration tests for the notifications view (FR-12)."""

    @classmethod
    def setUpTestData(cls):
        cls.user = make_user("view_user@notif.com")
        cls.admin = make_user("view_admin@notif.com", role=User.Role.ADMIN)
        cls.other_user = make_user("other_view@notif.com")
        cls.url = reverse("complaints:notifications")

    def setUp(self):
        self.complaint = make_complaint(self.user)
        Notification.objects.all().delete()

    # --- authentication & authorisation ---

    def test_unauthenticated_user_is_redirected_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_admin_gets_403(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_user_gets_200(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    # --- mark-as-read on visit ---

    def test_visiting_marks_all_unread_as_read(self):
        Notification.objects.create(
            user=self.user, complaint=self.complaint, message="msg1"
        )
        Notification.objects.create(
            user=self.user, complaint=self.complaint, message="msg2"
        )
        self.client.force_login(self.user)
        self.client.get(self.url)
        unread = Notification.objects.filter(user=self.user, is_read=False).count()
        self.assertEqual(unread, 0)

    def test_visiting_marks_only_own_notifications_as_read(self):
        other_complaint = make_complaint(self.other_user)
        Notification.objects.create(
            user=self.other_user, complaint=other_complaint, message="other msg"
        )
        self.client.force_login(self.user)
        self.client.get(self.url)
        # other user's notification must remain unread
        self.assertEqual(
            Notification.objects.filter(user=self.other_user, is_read=False).count(), 1
        )

    def test_already_read_notifications_remain_read(self):
        Notification.objects.create(
            user=self.user, complaint=self.complaint, message="old", is_read=True
        )
        self.client.force_login(self.user)
        self.client.get(self.url)
        self.assertEqual(
            Notification.objects.filter(user=self.user, is_read=True).count(), 1
        )

    # --- content ---

    def test_notifications_page_shows_own_notifications(self):
        Notification.objects.create(
            user=self.user, complaint=self.complaint, message="Your complaint changed."
        )
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertContains(response, "Your complaint changed.")

    def test_notifications_page_does_not_show_other_users_notifications(self):
        other_complaint = make_complaint(self.other_user)
        Notification.objects.create(
            user=self.other_user, complaint=other_complaint, message="Secret message."
        )
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertNotContains(response, "Secret message.")

    def test_empty_notifications_shows_no_notifications_message(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertContains(response, "no notifications")

    def test_unread_notification_shows_new_label(self):
        Notification.objects.create(
            user=self.user, complaint=self.complaint, message="A message."
        )
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertContains(response, "New")

    def test_read_notification_does_not_show_new_label(self):
        Notification.objects.create(
            user=self.user, complaint=self.complaint, message="A message.", is_read=True
        )
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertNotContains(response, "New")

    # --- pagination ---

    def test_pagination_shows_20_per_page(self):
        for i in range(25):
            Notification.objects.create(
                user=self.user, complaint=self.complaint, message=f"msg {i}"
            )
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(len(response.context["page"].object_list), 20)

    def test_pagination_second_page_accessible(self):
        for i in range(25):
            Notification.objects.create(
                user=self.user, complaint=self.complaint, message=f"msg {i}"
            )
        self.client.force_login(self.user)
        response = self.client.get(self.url + "?page=2")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["page"].object_list), 5)


# ---------------------------------------------------------------------------
# Context processor: navbar unread count
# ---------------------------------------------------------------------------

class NavbarUnreadCountTests(TestCase):
    """The unread_notification_count context variable drives the navbar badge."""

    @classmethod
    def setUpTestData(cls):
        cls.user = make_user("nav_user@notif.com")
        cls.admin = make_user("nav_admin@notif.com", role=User.Role.ADMIN)

    def setUp(self):
        self.complaint = make_complaint(self.user)
        Notification.objects.all().delete()
        # Use my_complaints as a stable USER-accessible page to check context
        self.page_url = reverse("complaints:my_list")

    def test_unread_count_reflects_unread_notifications(self):
        Notification.objects.create(
            user=self.user, complaint=self.complaint, message="m1"
        )
        Notification.objects.create(
            user=self.user, complaint=self.complaint, message="m2"
        )
        self.client.force_login(self.user)
        response = self.client.get(self.page_url)
        self.assertEqual(response.context["unread_notification_count"], 2)

    def test_unread_count_is_zero_when_all_read(self):
        Notification.objects.create(
            user=self.user, complaint=self.complaint, message="m1", is_read=True
        )
        self.client.force_login(self.user)
        response = self.client.get(self.page_url)
        self.assertEqual(response.context["unread_notification_count"], 0)

    def test_unread_count_is_zero_for_admin(self):
        # Admins don't get notifications; count must be 0
        self.client.force_login(self.admin)
        response = self.client.get(reverse("complaints:admin_list"))
        self.assertEqual(response.context["unread_notification_count"], 0)

    def test_unread_count_decreases_after_visiting_notifications(self):
        Notification.objects.create(
            user=self.user, complaint=self.complaint, message="m1"
        )
        self.client.force_login(self.user)
        # Before visit
        response = self.client.get(self.page_url)
        self.assertEqual(response.context["unread_notification_count"], 1)
        # Visit notifications page (marks as read)
        self.client.get(reverse("complaints:notifications"))
        # After visit
        response = self.client.get(self.page_url)
        self.assertEqual(response.context["unread_notification_count"], 0)

    def test_navbar_badge_rendered_when_unread_count_nonzero(self):
        Notification.objects.create(
            user=self.user, complaint=self.complaint, message="m1"
        )
        Notification.objects.create(
            user=self.user, complaint=self.complaint, message="m2"
        )
        Notification.objects.create(
            user=self.user, complaint=self.complaint, message="m3"
        )
        self.client.force_login(self.user)
        response = self.client.get(self.page_url)
        self.assertContains(response, "Notifications (3)")

    def test_navbar_badge_absent_when_count_is_zero(self):
        self.client.force_login(self.user)
        response = self.client.get(self.page_url)
        self.assertContains(response, "Notifications")
        self.assertNotContains(response, "Notifications (")
