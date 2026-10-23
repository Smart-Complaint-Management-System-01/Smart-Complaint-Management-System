import time

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.urls import reverse

from complaints.models import Complaint
from config.middleware import ResponseTimeMiddleware

User = get_user_model()

MAX_SECONDS = 3.0     # NFR-01 limit
USERS = 20            # "normal load" used in these tests
COMPLAINTS = 300


class ResponseTimeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="admin@x.com", email="admin@x.com", password="Pass12345!", role=User.Role.ADMIN
        )
        users = [
            User.objects.create_user(username=f"u{i}@x.com", email=f"u{i}@x.com", password="Pass12345!")
            for i in range(USERS)
        ]
        Complaint.objects.bulk_create([
            Complaint(
                complaint_id=f"CMP-{i + 1:06d}",
                user=users[i % USERS],
                category="OTHER",
                title=f"Seed complaint {i}",
                description="Seed data used for performance testing of the system.",
            )
            for i in range(COMPLAINTS)
        ])
        cls.first = Complaint.objects.first()

    def timed_get(self, url):
        start = time.perf_counter()
        response = self.client.get(url)
        elapsed = time.perf_counter() - start
        print(f"  {url:<35} {response.status_code}  {elapsed * 1000:6.0f} ms")  # for the test report
        return response, elapsed

    def test_public_and_admin_pages_respond_within_3_seconds(self):
        self.client.force_login(self.admin)
        urls = [
            reverse("home"),
            reverse("complaints:admin_list"),
            reverse("complaints:admin_list") + "?page=30",
            reverse("complaints:admin_detail", args=[self.first.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                response, elapsed = self.timed_get(url)
                self.assertEqual(response.status_code, 200)
                self.assertLess(elapsed, MAX_SECONDS)

    def test_admin_list_query_count_does_not_grow_with_data(self):
        self.client.force_login(self.admin)
        with CaptureQueriesContext(connection) as ctx:
            self.client.get(reverse("complaints:admin_list"))
        self.assertLess(len(ctx), 10)  # no N+1 queries for 10 rows per page

    def test_every_response_carries_a_timing_header(self):
        response = self.client.get(reverse("home"))
        self.assertRegex(response["X-Response-Time"], r"^\d+ms$")


class SlowRequestLoggingTests(TestCase):
    def test_slow_requests_are_logged_as_warnings(self):
        def slow_view(request):
            time.sleep(0.05)
            return HttpResponse("ok")

        with override_settings(SLOW_REQUEST_SECONDS=0.01):
            middleware = ResponseTimeMiddleware(slow_view)
        with self.assertLogs("performance", level="WARNING") as logs:
            middleware(RequestFactory().get("/slow/"))
        self.assertIn("SLOW REQUEST", logs.output[0])