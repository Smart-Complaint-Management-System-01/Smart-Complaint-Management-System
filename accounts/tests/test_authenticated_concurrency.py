import csv
import json
import os
from pathlib import Path
import platform
import sys
import tempfile

import django
from django.contrib.auth import get_user_model
from django.core.servers.basehttp import ThreadedWSGIServer
from django.db import connection
from django.test import LiveServerTestCase, override_settings
from django.test.testcases import LiveServerThread

from performance.load_test import Credential, run_load_test


def _write_csv_report(report_path, report):
    row = {
        "requirement": report["requirement"],
        "started_at_utc": report["started_at_utc"],
        "server": report["environment"]["server"],
        "database": report["environment"]["database"],
        "python": report["environment"]["python"],
        "django": report["environment"]["django"],
        "platform": report["environment"]["platform"],
        "configured_concurrency": report["configured_concurrency"],
        "authenticated_clients": report["authenticated_clients"],
        "requested_requests": report["requested_requests"],
        "completed_requests": report["completed_requests"],
        "successful_requests": report["successful_requests"],
        "failed_requests": report["failed_requests"],
        "elapsed_seconds": report["elapsed_seconds"],
        "throughput_requests_per_second": report[
            "throughput_requests_per_second"
        ],
        "median_latency_ms": report["latency_ms"]["median"],
        "p95_latency_ms": report["latency_ms"]["p95"],
        "max_latency_ms": report["latency_ms"]["max"],
        "slow_request_threshold_ms": report["latency_ms"]["threshold"],
        "slow_requests": report["slow_requests"],
        "passed": report["passed"],
        "status_counts": json.dumps(report["status_counts"]),
    }
    csv_path = Path(report_path).with_suffix(".csv")
    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=row)
        writer.writeheader()
        writer.writerow(row)


class HighConcurrencyLiveServer(ThreadedWSGIServer):
    request_queue_size = 256


class HighConcurrencyLiveServerThread(LiveServerThread):
    server_class = HighConcurrencyLiveServer


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AuthenticatedConcurrencyTests(LiveServerTestCase):
    server_thread_class = HighConcurrencyLiveServerThread

    def setUp(self):
        password = "Nfr02TestPassword!"
        user_model = get_user_model()
        users = []
        self.credentials = []
        for number in range(100):
            email = f"nfr02-live-{number:03d}@example.test"
            user = user_model(username=email, email=email)
            user.set_password(password)
            users.append(user)
            self.credentials.append(Credential(email=email, password=password))
        user_model.objects.bulk_create(users)

    def test_100_distinct_authenticated_users_can_request_protected_page(self):
        with tempfile.TemporaryDirectory() as directory:
            report_path = os.environ.get("NFR02_REPORT_PATH")
            report = run_load_test(
                target_url=f"{self.live_server_url}/complaints/",
                credentials=self.credentials,
                request_count=100,
                concurrency=100,
                threshold_seconds=30,
                report_path=(
                    Path(report_path)
                    if report_path
                    else Path(directory) / "nfr02-live-server.json"
                ),
                report_metadata={
                    "server": "Django threaded live test server",
                    "database": connection.vendor,
                    "python": sys.version.split()[0],
                    "django": django.get_version(),
                    "platform": platform.platform(),
                },
            )
            if report_path:
                _write_csv_report(report_path, report)

        self.assertTrue(report["passed"], report)
        self.assertEqual(report["authenticated_clients"], 100)
        self.assertEqual(report["completed_requests"], 100)
        self.assertEqual(report["successful_requests"], 100)
        self.assertEqual(report["failed_requests"], 0)
