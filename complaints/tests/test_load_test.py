import csv
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
from threading import Event, Lock, Thread
from uuid import uuid4
from urllib.parse import parse_qs, urlsplit

from django.test import SimpleTestCase

from performance.load_test import Credential, load_credentials, run_load_test


class AuthenticatedLoadRunnerTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.password = "LoadTestPass123!"
        cls.valid_credentials = {
            f"test-user-{number:03d}@example.test": cls.password
            for number in range(100)
        }
        cls.sessions = {}
        cls.sessions_lock = Lock()
        cls.concurrent_arrivals = 0
        cls.max_concurrent_arrivals = 0
        cls.arrivals_lock = Lock()
        cls.all_clients_arrived = Event()
        cls.force_request_failures = False
        cls.redirect_measured_requests = False

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, _format_string, *_args):
                del _format_string, _args
                return

            def _respond(self, status, body=b"", headers=None):
                self.send_response(status)
                for key, value in (headers or {}).items():
                    self.send_header(key, value)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if body:
                    self.wfile.write(body)

            def do_GET(self):
                path = urlsplit(self.path).path
                if path == "/login/":
                    body = (
                        b'<form><input name="csrfmiddlewaretoken" value="test-csrf">'
                        b"</form>"
                    )
                    self._respond(
                        200,
                        body,
                        {"Set-Cookie": "csrftoken=test-csrf; Path=/"},
                    )
                    return

                if path == "/dashboard/":
                    cookie = SimpleCookie(self.headers.get("Cookie", ""))
                    session = cookie.get("sessionid")
                    with AuthenticatedLoadRunnerTests.sessions_lock:
                        authenticated = (
                            session
                            and session.value in AuthenticatedLoadRunnerTests.sessions
                        )
                    if authenticated:
                        self._respond(200, b"dashboard")
                    else:
                        self.send_response(302)
                        self.send_header("Location", "/login/")
                        self.end_headers()
                    return

                if path == "/complaints/":
                    cookie = SimpleCookie(self.headers.get("Cookie", ""))
                    session = cookie.get("sessionid")
                    with AuthenticatedLoadRunnerTests.sessions_lock:
                        authenticated = (
                            session
                            and session.value in AuthenticatedLoadRunnerTests.sessions
                        )
                    if not authenticated:
                        self.send_response(302)
                        self.send_header("Location", "/login/")
                        self.end_headers()
                        return

                    is_probe = self.headers.get("X-Load-Test-Probe") == "preflight"
                    if (
                        not is_probe
                        and AuthenticatedLoadRunnerTests.redirect_measured_requests
                    ):
                        self.send_response(302)
                        self.send_header("Location", "/login/")
                        self.end_headers()
                        return
                    if not is_probe:
                        with AuthenticatedLoadRunnerTests.arrivals_lock:
                            AuthenticatedLoadRunnerTests.concurrent_arrivals += 1
                            AuthenticatedLoadRunnerTests.max_concurrent_arrivals = max(
                                AuthenticatedLoadRunnerTests.max_concurrent_arrivals,
                                AuthenticatedLoadRunnerTests.concurrent_arrivals,
                            )
                            if (
                                AuthenticatedLoadRunnerTests.concurrent_arrivals >= 100
                            ):
                                AuthenticatedLoadRunnerTests.all_clients_arrived.set()
                        AuthenticatedLoadRunnerTests.all_clients_arrived.wait(
                            timeout=15
                        )
                    self._respond(
                        (
                            503
                            if AuthenticatedLoadRunnerTests.force_request_failures
                            and not is_probe
                            else 200
                        ),
                        b"unavailable"
                        if AuthenticatedLoadRunnerTests.force_request_failures
                        and not is_probe
                        else b"protected",
                        {"X-Response-Time": "1.00ms"},
                    )
                    if not is_probe:
                        with AuthenticatedLoadRunnerTests.arrivals_lock:
                            AuthenticatedLoadRunnerTests.concurrent_arrivals -= 1
                    return

                self._respond(404)

            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                form = parse_qs(self.rfile.read(length).decode())
                email = form.get("email", [""])[0]
                password = form.get("password", [""])[0]
                if (
                    AuthenticatedLoadRunnerTests.valid_credentials.get(email)
                    != password
                ):
                    self.send_response(302)
                    self.send_header("Location", "/login/")
                    self.end_headers()
                    return

                session_id = uuid4().hex
                with AuthenticatedLoadRunnerTests.sessions_lock:
                    AuthenticatedLoadRunnerTests.sessions[session_id] = email
                self.send_response(302)
                self.send_header("Location", "/dashboard/")
                self.send_header("Set-Cookie", f"sessionid={session_id}; Path=/")
                self.end_headers()

        class LoadTestHTTPServer(ThreadingHTTPServer):
            request_queue_size = 256

        cls.server = LoadTestHTTPServer(("127.0.0.1", 0), Handler)
        cls.server_thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.server_thread.join(timeout=5)
        with cls.sessions_lock:
            cls.sessions.clear()
        super().tearDownClass()

    def test_load_test_requires_100_unique_accounts(self):
        with self.assertRaisesRegex(ValueError, "credential"):
            run_load_test(
                f"{self.base_url}/complaints/",
                [Credential("one@example.test", self.password)],
                request_count=100,
                concurrency=100,
                threshold_seconds=3,
                report_path=Path(tempfile.gettempdir()) / "unused-report.json",
            )

    def test_100_authenticated_users_are_tested_and_report_is_saved(self):
        with self.arrivals_lock:
            type(self).concurrent_arrivals = 0
            type(self).max_concurrent_arrivals = 0
            type(self).all_clients_arrived.clear()

        with tempfile.TemporaryDirectory() as directory:
            users_path = Path(directory) / "users.csv"
            report_path = Path(directory) / "nfr02.json"
            with users_path.open("w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=["email", "password"])
                writer.writeheader()
                writer.writerows(
                    {"email": email, "password": password}
                    for email, password in self.valid_credentials.items()
                )
            credentials = load_credentials(users_path, 100)
            report = run_load_test(
                f"{self.base_url}/complaints/?token=do-not-record",
                credentials,
                request_count=200,
                concurrency=100,
                threshold_seconds=3,
                report_path=report_path,
            )
            saved_report_text = report_path.read_text(encoding="utf-8")
            saved_report = json.loads(saved_report_text)

        self.assertTrue(report["passed"], report)
        self.assertEqual(report["authenticated_clients"], 100, report)
        self.assertEqual(report["successful_requests"], 200)
        self.assertEqual(report["failed_requests"], 0)
        self.assertEqual(report["slow_requests"], 0)
        self.assertEqual(saved_report, report)
        self.assertNotIn(self.password, saved_report_text)
        self.assertNotIn("do-not-record", saved_report_text)
        self.assertEqual(self.max_concurrent_arrivals, 100)

    def test_authentication_failures_fail_the_run(self):
        credentials = [
            Credential(email, password)
            for email, password in self.valid_credentials.items()
        ]
        credentials[-1] = Credential(credentials[-1].email, "incorrect-password")

        with tempfile.TemporaryDirectory() as directory:
            report = run_load_test(
                f"{self.base_url}/complaints/",
                credentials,
                request_count=100,
                concurrency=100,
                threshold_seconds=3,
                report_path=Path(directory) / "auth-failure.json",
            )

        self.assertFalse(report["passed"])
        self.assertLess(report["authenticated_clients"], 100)
        self.assertTrue(report["client_setup_errors"])
        self.assertEqual(report["completed_requests"], 0)

    def test_slow_requests_are_recorded_and_fail_the_run(self):
        credentials = [
            Credential(email, password)
            for email, password in self.valid_credentials.items()
        ]
        with self.arrivals_lock:
            type(self).concurrent_arrivals = 0
            type(self).max_concurrent_arrivals = 0
            type(self).all_clients_arrived.clear()

        with tempfile.TemporaryDirectory() as directory:
            report = run_load_test(
                f"{self.base_url}/complaints/",
                credentials,
                request_count=100,
                concurrency=100,
                threshold_seconds=0.000001,
                report_path=Path(directory) / "slow-run.json",
            )

        self.assertFalse(report["passed"])
        self.assertEqual(report["slow_requests"], 100)
        self.assertEqual(len(report["slow_request_details"]), 100)

    def test_expired_sessions_are_not_counted_as_successful_requests(self):
        credentials = [
            Credential(email, password)
            for email, password in self.valid_credentials.items()
        ]
        with self.arrivals_lock:
            type(self).concurrent_arrivals = 0
            type(self).max_concurrent_arrivals = 0
            type(self).all_clients_arrived.clear()
            type(self).redirect_measured_requests = True

        try:
            with tempfile.TemporaryDirectory() as directory:
                report = run_load_test(
                    f"{self.base_url}/complaints/",
                    credentials,
                    request_count=100,
                    concurrency=100,
                    threshold_seconds=3,
                    report_path=Path(directory) / "expired-sessions.json",
                )
        finally:
            type(self).redirect_measured_requests = False

        self.assertFalse(report["passed"])
        self.assertEqual(report["failed_requests"], 100)
        self.assertTrue(
            all(
                "redirected to /login" in failure["error"]
                for failure in report["failures"]
            )
        )

    def test_request_failures_are_recorded_and_fail_the_load_test(self):
        credentials = [
            Credential(email, password)
            for email, password in self.valid_credentials.items()
        ]
        with self.arrivals_lock:
            type(self).concurrent_arrivals = 0
            type(self).max_concurrent_arrivals = 0
            type(self).all_clients_arrived.clear()
            type(self).force_request_failures = True

        try:
            with tempfile.TemporaryDirectory() as directory:
                report = run_load_test(
                    f"{self.base_url}/complaints/",
                    credentials,
                    request_count=100,
                    concurrency=100,
                    threshold_seconds=3,
                    report_path=Path(directory) / "failed-run.json",
                )
        finally:
            type(self).force_request_failures = False

        self.assertFalse(report["passed"])
        self.assertEqual(report["authenticated_clients"], 100, report)
        self.assertEqual(report["failed_requests"], 100)
        self.assertEqual(report["status_counts"]["503"], 100)

    def test_credentials_file_requires_unique_emails(self):
        with tempfile.TemporaryDirectory() as directory:
            csv_path = Path(directory) / "users.csv"
            with csv_path.open("w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(["email", "password"])
                writer.writerow(["same@example.test", "one"])
                writer.writerow(["SAME@example.test", "two"])

            with self.assertRaisesRegex(ValueError, "duplicate email"):
                load_credentials(csv_path, 2)
