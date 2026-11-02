from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import DatabaseError
from django.test import TestCase
from django.urls import reverse

from complaints.models import Complaint


class SubmitRecoveryTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="submitter@example.com",
            email="submitter@example.com",
            password="SecurePass123!",
        )
        self.client.force_login(self.user)
        self.url = reverse("complaints:new")

    def _submission_data(self):
        self.client.get(self.url)
        return {
            "category": Complaint.Category.INFRASTRUCTURE,
            "title": "Broken switch",
            "description": "The switch in lab 3 is broken.",
            "form_token": self.client.session["complaint_form_token"],
        }

    def test_database_failure_shows_error_and_creates_no_record(self):
        data = self._submission_data()
        with patch.object(Complaint, "save", side_effect=DatabaseError):
            response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, 500)
        self.assertContains(response, "save your complaint", status_code=500)
        self.assertNotContains(response, "submitted successfully", status_code=500)
        self.assertEqual(Complaint.objects.count(), 0)

    def test_failed_transaction_does_not_change_existing_complaints(self):
        existing = Complaint.objects.create(
            user=self.user,
            category=Complaint.Category.ACADEMIC,
            title="Existing complaint",
            description="Keep this complaint unchanged.",
        )
        data = self._submission_data()
        original_save = Complaint.save

        def save_then_fail(complaint, *args, **kwargs):
            original_save(complaint, *args, **kwargs)
            raise DatabaseError("Simulated failure after insert")

        with patch.object(Complaint, "save", save_then_fail):
            response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, 500)
        self.assertEqual(Complaint.objects.count(), 1)
        existing.refresh_from_db()
        self.assertEqual(existing.title, "Existing complaint")
        self.assertEqual(existing.description, "Keep this complaint unchanged.")

    def test_retry_after_failure_saves_once(self):
        data = self._submission_data()
        with patch.object(Complaint, "save", side_effect=DatabaseError):
            self.client.post(self.url, data)

        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Complaint.objects.count(), 1)

    def test_replayed_token_does_not_create_duplicate(self):
        data = self._submission_data()
        first_response = self.client.post(self.url, data)
        self.assertEqual(first_response.status_code, 302)

        # Simulate a concurrent request that passed the session-token check
        # before the first request consumed the token.
        session = self.client.session
        session["complaint_form_token"] = data["form_token"]
        session.save()
        replay_response = self.client.post(self.url, data)

        self.assertEqual(replay_response.status_code, 302)
        self.assertEqual(Complaint.objects.count(), 1)
