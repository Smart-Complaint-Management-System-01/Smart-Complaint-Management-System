import csv
import getpass
import os
from pathlib import Path
import tempfile

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, transaction

from accounts.models import User


class Command(BaseCommand):
    help = "Create or remove local-only users for authenticated load testing."

    def add_arguments(self, parser):
        parser.add_argument("--confirm-local", action="store_true")
        parser.add_argument("--count", type=int, default=100)
        parser.add_argument("--cleanup", action="store_true")

    def handle(self, *args, **options):
        del args
        output_path = Path(settings.BASE_DIR) / "performance" / "test-users.csv"
        database_host = settings.DATABASES["default"].get("HOST", "")
        if not options["confirm_local"] or database_host not in {
            "",
            "localhost",
            "127.0.0.1",
            "::1",
        }:
            raise CommandError(
                "This command is restricted to a confirmed local database. "
                "Use --confirm-local with DB_HOST set to localhost."
            )

        if options["cleanup"]:
            self._cleanup(output_path)
            return

        count = options["count"]
        if count < 100:
            raise CommandError("--count must be at least 100.")

        output_path = output_path.resolve()
        if output_path.exists():
            raise CommandError(f"{output_path} already exists; refusing to overwrite it.")

        password = getpass.getpass("Password for the temporary load-test accounts: ")
        if not password:
            raise CommandError("A non-empty test password is required.")

        email_addresses = [
            f"nfr02-user-{number:03d}@example.test"
            for number in range(1, count + 1)
        ]
        if User.objects.filter(email__in=email_addresses).exists():
            raise CommandError(
                "At least one load-test email already exists. "
                "Run this command with --cleanup before reseeding."
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = None
        output_created = False
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                newline="",
                dir=output_path.parent,
                prefix=f".{output_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as file:
                temporary_path = Path(file.name)
                writer = csv.DictWriter(file, fieldnames=["email", "password"])
                writer.writeheader()
                writer.writerows(
                    {"email": email, "password": password}
                    for email in email_addresses
                )

            users = []
            for email in email_addresses:
                user = User(username=email, email=email)
                user.set_password(password)
                users.append(user)

            with transaction.atomic():
                User.objects.bulk_create(users)
                os.replace(temporary_path, output_path)
                output_created = True
        except (DatabaseError, OSError, ValueError, RuntimeError) as exc:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            if output_created:
                output_path.unlink(missing_ok=True)
            raise CommandError(
                "Could not create load-test accounts and credentials file."
            ) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Created {count} local load-test accounts. "
                f"Credentials saved to {output_path}. Keep this file private."
            )
        )

    def _cleanup(self, credentials_path):
        deleted_count, _ = User.objects.filter(
            username__startswith="nfr02-user-",
            email__endswith="@example.test",
        ).delete()
        credentials_path.unlink(missing_ok=True)
        self.stdout.write(
            self.style.SUCCESS(f"Removed {deleted_count} local load-test accounts.")
        )
