from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import DatabaseError
from django.test import TestCase
from django.urls import reverse

from complaints.models import Complaint


class SubmitRecoveryTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="sub@example.com", email="sub@example.com", password="Pass@12345"
        )                                    # add role=User.Role.USER if it isn't the default
        self.client.force_login(self.user)
        self.url = reverse("complaints:new")  # check the url name in complaints/urls.py

    def _data(self):
        self.client.get(self.url)             # issues the token
        return {
            "title": "Broken switch",         # match your ComplaintForm fields
            "description": "The switch in lab 3 is broken.",
            "category": Complaint.Category.INFRASTRUCTURE,
            "form_token": self.client.session["complaint_form_token"],
        }

    def test_failed_submission_creates_no_record(self):
        data = self._data()
        with patch.object(Complaint, "save", side_effect=DatabaseError):
            r = self.client.post(self.url, data)
        self.assertEqual(r.status_code, 500)
        self.assertEqual(Complaint.objects.count(), 0)

    def test_failure_is_not_reported_as_success(self):
        data = self._data()
        with patch.object(Complaint, "save", side_effect=DatabaseError):
            r = self.client.post(self.url, data)
        self.assertNotContains(r, "submitted successfully", status_code=500)
        self.assertContains(r, "couldn", status_code=500)

    def test_double_post_creates_one_record(self):
        data = self._data()
        self.client.post(self.url, data)
        self.client.post(self.url, data)      # same token again
        self.assertEqual(Complaint.objects.count(), 1)

    def test_retry_after_failure_works(self):
        data = self._data()
        with patch.object(Complaint, "save", side_effect=DatabaseError):
            self.client.post(self.url, data)
        self.client.post(self.url, data)      # token was not consumed by the failure
        self.assertEqual(Complaint.objects.count(), 1)