from datetime import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from complaints.models import Complaint
from complaints.search import ComplaintFilterForm, filter_complaints

User = get_user_model()


class SearchFilterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="u@x.com", email="u@x.com", password="Pass12345!")
        cls.admin = User.objects.create_user(
            username="a@x.com", email="a@x.com", password="Pass12345!", role=User.Role.ADMIN
        )
        cls.hostel = Complaint.objects.create(user=cls.user, category="HOSTEL", title="Leak", description="d")
        cls.academic = Complaint.objects.create(
            user=cls.user, category="ACADEMIC", title="Marks", description="d", status="UNDER_REVIEW"
        )
        Complaint.objects.filter(pk=cls.hostel.pk).update(
            created_at=timezone.make_aware(datetime(2026, 9, 1, 10, 0))
        )

    def run_filter(self, **data):
        form = ComplaintFilterForm(data)
        self.assertTrue(form.is_valid(), form.errors)
        return list(filter_complaints(Complaint.objects.all(), form.cleaned_data))

    def test_filter_by_complaint_id(self):
        self.assertEqual(self.run_filter(complaint_id=self.hostel.complaint_id), [self.hostel])

    def test_filter_by_category(self):
        self.assertEqual(self.run_filter(category="ACADEMIC"), [self.academic])

    def test_filter_by_status(self):
        self.assertEqual(self.run_filter(status="UNDER_REVIEW"), [self.academic])

    def test_filter_by_date_range(self):
        self.assertEqual(self.run_filter(from_date="2026-09-01", to_date="2026-09-01"), [self.hostel])

    def test_combined_filters(self):
        self.assertEqual(self.run_filter(category="HOSTEL", status="UNDER_REVIEW"), [])

    def test_inverted_date_range_is_invalid(self):
        self.assertFalse(ComplaintFilterForm({"from_date": "2026-10-02", "to_date": "2026-10-01"}).is_valid())

    def test_admin_list_view_filters_and_shows_empty_message(self):
        self.client.force_login(self.admin)
        url = reverse("complaints:admin_list")
        self.assertContains(self.client.get(url, {"category": "ACADEMIC"}), "Marks")
        self.assertNotContains(self.client.get(url, {"category": "ACADEMIC"}), "Leak")
        self.assertContains(self.client.get(url, {"category": "TRANSPORT"}), "No complaints match your search.")

    def test_user_gets_403_on_admin_search(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("complaints:admin_list"), {"status": "SUBMITTED"}).status_code, 403)