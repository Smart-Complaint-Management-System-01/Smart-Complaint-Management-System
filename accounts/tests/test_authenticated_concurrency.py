from pathlib import Path
import tempfile

from django.contrib.auth import get_user_model
from django.core.servers.basehttp import ThreadedWSGIServer
from django.test import LiveServerTestCase, override_settings
from django.test.testcases import LiveServerThread

from performance.load_test import Credential, run_load_test


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
            report = run_load_test(
                target_url=f"{self.live_server_url}/complaints/",
                credentials=self.credentials,
                request_count=100,
                concurrency=100,
                threshold_seconds=30,
                report_path=Path(directory) / "nfr02-live-server.json",
            )

        self.assertTrue(report["passed"], report)
        self.assertEqual(report["authenticated_clients"], 100)
        self.assertEqual(report["completed_requests"], 100)
        self.assertEqual(report["successful_requests"], 100)
        self.assertEqual(report["failed_requests"], 0)
