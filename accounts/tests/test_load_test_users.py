from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings


class SeedLoadTestUsersCommandTests(SimpleTestCase):
    @override_settings(DATABASES={"default": {"HOST": "localhost"}})
    def test_seed_command_requires_at_least_100_users(self):
        with self.assertRaisesRegex(CommandError, "at least 100"):
            call_command(
                "seed_load_test_users",
                confirm_local=True,
                count=99,
            )

    @override_settings(DATABASES={"default": {"HOST": "localhost"}})
    def test_seed_command_requires_local_confirmation(self):
        with self.assertRaisesRegex(CommandError, "confirmed local database"):
            call_command("seed_load_test_users", count=100)
