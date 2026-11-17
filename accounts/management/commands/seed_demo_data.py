from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import User
from complaints import services
from complaints.models import Complaint, Department

DEMO_DOMAIN = "@scms.test"
DEFAULT_PASSWORD = "Demo@2026"
DEFAULT_ADMINS = 2
DEFAULT_USERS = 5

S = Complaint.Status
C = Complaint.Category

# (owner, category, title, description, target status, department, assignee)
COMPLAINTS = [
    ("user_1", C.HOSTEL, "Water leakage in Block B room 214",
     "Water has been leaking from the ceiling near the window for three days.",
     S.SUBMITTED, None, None),
    ("user_1", C.ACADEMIC, "Internal marks not updated on portal",
     "ISA-2 marks for Software Engineering are still missing on the student portal.",
     S.UNDER_REVIEW, None, None),
    ("user_2", C.INFRASTRUCTURE, "Projector not working in room 1003",
     "The projector in classroom 1003 does not turn on; lectures are being delayed.",
     S.ASSIGNED, "Infrastructure & Maintenance", "admin_1"),
    ("user_2", C.TRANSPORT, "Bus route 7 consistently late",
     "The 7:30 AM bus on route 7 has arrived 20+ minutes late all week.",
     S.IN_PROGRESS, "Transport Office", "admin_2"),
    ("user_3", C.HOSTEL, "Wi-Fi down on hostel 3rd floor",
     "No Wi-Fi connectivity on the 3rd floor of the boys' hostel since Monday.",
     S.RESOLVED, "Hostel Administration", "admin_1"),
    ("user_3", C.ADMINISTRATIVE, "Fee receipt not generated",
     "Paid the semester fee online but no receipt was generated.",
     S.REJECTED, None, None),
    ("user_1", C.OTHER, "Canteen hygiene concern",
     "Drinking water dispenser in the main canteen is not cleaned regularly.",
     S.CLOSED, "Administrative Office", "admin_2"),
]


class Command(BaseCommand):
    help = "Create demo admin/user accounts and sample complaints for presentations."

    def add_arguments(self, parser):
        parser.add_argument("--password", default=DEFAULT_PASSWORD)
        parser.add_argument("--reset", action="store_true",
                            help="Delete existing demo data before seeding.")
        parser.add_argument("--remove", action="store_true",
                            help="Delete demo data and exit.")
        parser.add_argument("--admins", type=int, default=DEFAULT_ADMINS,
                            help="Number of admin_N accounts (min 2).")
        parser.add_argument("--users", type=int, default=DEFAULT_USERS,
                            help="Number of user_N accounts (min 3).")

    def handle(self, *args, **opts):
        if not settings.DEBUG:
            raise CommandError("Refusing to seed demo accounts with DEBUG=False.")

        if opts["remove"] or opts["reset"]:
            n, _ = User.objects.filter(email__endswith=DEMO_DOMAIN).delete()
            self.stdout.write(f"Removed demo data ({n} rows incl. complaints/history).")
            if opts["remove"]:
                return

        # sample complaints reference user_1..user_3 and admin_1..admin_2
        n_admins = max(opts["admins"], 2)
        n_users = max(opts["users"], 3)
        accounts = ([(f"admin_{i}", "Admin", str(i), User.Role.ADMIN) for i in range(1, n_admins + 1)]
                    + [(f"user_{i}", "User", str(i), User.Role.USER) for i in range(1, n_users + 1)])

        with transaction.atomic():
            users = {}
            for username, first, last, role in accounts:
                users[username] = self._user(username, first, last, role, opts["password"])

            created = 0
            for owner, cat, title, desc, target, dept, assignee in COMPLAINTS:
                if Complaint.objects.filter(user=users[owner], title=title).exists():
                    continue
                c = Complaint.objects.create(user=users[owner], category=cat,
                                             title=title, description=desc)
                services.record_initial_status(c, actor=users[owner])
                self._advance(c, target, users, dept, assignee)
                created += 1

        self.stdout.write(self.style.SUCCESS(f"Demo complaints created: {created}"))
        self.stdout.write("\nLogin with email (or username) and password: " + opts["password"])
        for username, *_ in accounts:
            u = users[username]
            self.stdout.write(f"  {u.role:<5}  {u.username:<10}  {u.email}")

    def _user(self, username, first, last, role, password):
        user, _ = User.objects.get_or_create(
            username=username,
            defaults={"email": username + DEMO_DOMAIN, "first_name": first,
                      "last_name": last, "role": role},
        )
        user.set_password(password)
        user.save()
        return user

    def _advance(self, c, target, users, dept_name, assignee):
        """Walk the complaint through the real workflow so history + notifications exist."""
        admin = users[assignee] if assignee else users["admin_1"]
        if target == S.SUBMITTED:
            return
        if target == S.REJECTED:
            services.change_status(c, S.UNDER_REVIEW, admin, "Reviewing the complaint.")
            services.change_status(c, S.REJECTED, admin, "Duplicate of an earlier request; please contact the accounts office.")
            return
        services.change_status(c, S.UNDER_REVIEW, admin, "Complaint received and under review.")
        if target == S.UNDER_REVIEW:
            return
        dept = Department.objects.get_or_create(name=dept_name)[0] if dept_name else None
        services.assign_complaint(c, assigned_to=admin, department=dept, actor=admin)
        if target == S.ASSIGNED:
            return
        services.change_status(c, S.IN_PROGRESS, admin, "Work has started.")
        services.add_update(c, admin, "Technician visited; parts ordered.")
        if target == S.IN_PROGRESS:
            return
        services.resolve_complaint(c, "Issue fixed and verified with the complainant.", admin)
        if target == S.CLOSED:
            services.change_status(c, S.CLOSED, admin, "Closed after confirmation.")