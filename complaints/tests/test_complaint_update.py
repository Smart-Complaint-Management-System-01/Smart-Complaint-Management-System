from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from complaints.models import Complaint
from complaints.services import InvalidTransition, add_update

User = get_user_model()


class ComplaintUpdateServiceTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="u@x.com",
            email="u@x.com",
            password="Pass12345!",
        )

        cls.admin = User.objects.create_user(
            username="a@x.com",
            email="a@x.com",
            password="Pass12345!",
            role=User.Role.ADMIN,
        )

        cls.complaint = Complaint.objects.create(
            user=cls.user,
            category="OTHER",
            title="Test complaint",
            description="Test description",
        )

    def test_add_update_creates_history_without_changing_status(self):
        original_status = self.complaint.status

        add_update(
            self.complaint,
            self.admin,
            "Technician visited.",
        )

        entry = self.complaint.history.get()

        self.assertEqual(entry.previous_status, original_status)
        self.assertEqual(entry.new_status, original_status)
        self.assertEqual(entry.update_details, "Technician visited.")
        self.assertEqual(entry.updated_by, self.admin)

    def test_empty_note_is_rejected(self):
        with self.assertRaises(ValueError):
            add_update(self.complaint, self.admin, "  ")

    def test_resolved_complaint_cannot_be_updated(self):
        complaint = Complaint.objects.create(
            user=self.user,
            category="OTHER",
            title="Resolved complaint",
            description="Test description",
            status="RESOLVED",
        )

        with self.assertRaises(InvalidTransition):
            add_update(
                complaint,
                self.admin,
                "Late update",
            )

class ComplaintUpdateViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="owner@example.com",
            email="owner@example.com",
            password="Pass12345!",
        )
        cls.other_user = User.objects.create_user(
            username="other@example.com",
            email="other@example.com",
            password="Pass12345!",
        )
        cls.admin = User.objects.create_user(
            username="admin@example.com",
            email="admin@example.com",
            password="Pass12345!",
            role=User.Role.ADMIN,
        )

    def setUp(self):
        self.complaint = Complaint.objects.create(
            user=self.user,
            category=Complaint.Category.OTHER,
            title="Test complaint",
            description="Test description",
        )
        self.admin_url = reverse(
            "complaints:admin_add_update", args=[self.complaint.pk]
        )
        self.user_url = reverse(
            "complaints:add_info", args=[self.complaint.complaint_id]
        )

    def test_admin_can_add_update_and_history_records_actor(self):
        self.client.force_login(self.admin)

        response = self.client.post(self.admin_url, {"note": "Technician visited."})

        self.assertRedirects(
            response,
            reverse("complaints:admin_detail", args=[self.complaint.pk]),
        )
        entry = self.complaint.history.get()
        self.assertEqual(entry.updated_by, self.admin)
        self.assertEqual(entry.update_details, "Technician visited.")
        self.assertEqual(entry.previous_status, self.complaint.status)
        self.assertEqual(entry.new_status, self.complaint.status)

    def test_regular_user_cannot_use_admin_update_route(self):
        self.client.force_login(self.user)

        response = self.client.post(self.admin_url, {"note": "Unauthorized."})

        self.assertEqual(response.status_code, 403)
        self.assertFalse(self.complaint.history.exists())

    def test_admin_update_route_rejects_get(self):
        self.client.force_login(self.admin)

        self.assertEqual(self.client.get(self.admin_url).status_code, 405)

    def test_owner_can_add_information_to_own_complaint(self):
        self.client.force_login(self.user)

        response = self.client.post(self.user_url, {"note": "More details."})

        self.assertRedirects(
            response,
            reverse("complaints:complaint_detail", args=[self.complaint.complaint_id]),
        )
        entry = self.complaint.history.get()
        self.assertEqual(entry.updated_by, self.user)
        self.assertEqual(entry.update_details, "More details.")
        self.assertEqual(entry.previous_status, self.complaint.status)
        self.assertEqual(entry.new_status, self.complaint.status)

    def test_owner_cannot_update_another_users_complaint(self):
        other_complaint = Complaint.objects.create(
            user=self.other_user,
            category=Complaint.Category.OTHER,
            title="Private complaint",
            description="Private description",
        )
        url = reverse("complaints:add_info", args=[other_complaint.complaint_id])
        self.client.force_login(self.user)

        response = self.client.post(url, {"note": "Unauthorized."})

        self.assertEqual(response.status_code, 404)
        self.assertFalse(other_complaint.history.exists())

    def test_anonymous_owner_update_is_redirected_to_login(self):
        response = self.client.post(self.user_url, {"note": "More details."})

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])
        self.assertFalse(self.complaint.history.exists())

    def test_blank_update_note_shows_validation_feedback(self):
        self.client.force_login(self.user)

        response = self.client.post(self.user_url, {"note": "   "}, follow=True)

        self.assertContains(response, "Please enter an update note.")
        self.assertFalse(self.complaint.history.exists())

    def test_resolved_complaint_cannot_be_updated_through_view(self):
        self.complaint.status = Complaint.Status.RESOLVED
        self.complaint.save(update_fields=["status", "updated_at"])
        self.client.force_login(self.user)

        response = self.client.post(self.user_url, {"note": "Late details."}, follow=True)

        self.assertContains(response, "Resolved complaints cannot be updated.")
        self.assertFalse(self.complaint.history.exists())
