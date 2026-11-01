from django.contrib.auth import get_user_model
from django.test import TestCase

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