from django.core.management.base import BaseCommand

from complaints.models import Department

DEPARTMENTS = [
    "Academic Affairs",
    "Hostel Administration",
    "Infrastructure & Maintenance",
    "Transport Office",
    "Administrative Office",
]


class Command(BaseCommand):
    help = "Create the default departments (safe to run repeatedly)."

    def handle(self, *args, **options):
        for name in DEPARTMENTS:
            _, created = Department.objects.get_or_create(name=name)
            self.stdout.write(("Created " if created else "Exists  ") + name)
