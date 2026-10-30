from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from config.middleware import ResponseTimeMiddleware
from complaints.models import Complaint


class ResponseTimeMiddlewareTests(SimpleTestCase):
    def test_application_responses_include_response_time(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertRegex(response["X-Response-Time"], r"^\d+\.\d{2}ms$")

    @override_settings(SLOW_REQUEST_THRESHOLD_SECONDS=3)
    def test_slow_requests_are_logged_with_request_details(self):
        middleware = ResponseTimeMiddleware(lambda request: HttpResponse("ok"))
        request = RequestFactory().get("/complaints/")

        with patch("config.middleware.time.perf_counter", side_effect=[1.0, 4.5]):
            with self.assertLogs("performance", level="WARNING") as captured:
                response = middleware(request)

        self.assertEqual(response["X-Response-Time"], "3500.00ms")
        self.assertIn("GET /complaints/ returned 200", captured.output[0])
        self.assertIn("3500.00ms", captured.output[0])

    @override_settings(SLOW_REQUEST_THRESHOLD_SECONDS=3)
    def test_requests_under_threshold_are_not_logged_as_slow(self):
        middleware = ResponseTimeMiddleware(lambda request: HttpResponse("ok"))
        request = RequestFactory().get("/")

        with patch("config.middleware.time.perf_counter", side_effect=[1.0, 2.0]):
            response = middleware(request)

        self.assertEqual(response["X-Response-Time"], "1000.00ms")


class ComplaintListPerformanceTests(TestCase):
    def test_my_complaints_page_is_limited_to_ten_records(self):
        user = get_user_model().objects.create_user(
            username="performance-user",
            email="performance@example.com",
            password="SecurePass123!",
        )
        self.client.force_login(user)
        for index in range(11):
            Complaint.objects.create(
                user=user,
                category=Complaint.Category.OTHER,
                title=f"Complaint {index}",
                description="Complaint description for pagination testing.",
            )

        first_page = self.client.get(reverse("complaints:my_list"))
        second_page = self.client.get(reverse("complaints:my_list"), {"page": 2})

        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(len(first_page.context["complaints"]), 10)
        self.assertContains(first_page, "Page 1 of 2")
        self.assertEqual(len(second_page.context["complaints"]), 1)
        self.assertContains(second_page, "Page 2 of 2")
