
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from complaints.models import Complaint, Department
from complaints.services import assign_complaint, InvalidAssignment

User = get_user_model()


class ComplaintAssignmentTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="student1",
            email="student1@example.com",
            password=None,
        )

        self.admin = User.objects.create_user(
            username="admin1",
            email="admin1@example.com",
            password=None,
            role=User.Role.ADMIN,
            is_active=True,
        )

        self.department, created = Department.objects.get_or_create(
            name="Hostel"
        )

        self.complaint = Complaint.objects.create(
            user=self.user,
            category=Complaint.Category.HOSTEL,
            title="Water supply issue",
            description="The hostel water supply is not working.",
            status=Complaint.Status.UNDER_REVIEW,
        )

    def test_assignment_changes_under_review_to_assigned(self):
        assign_complaint(
            self.complaint,
            assigned_to=self.admin,
            department=self.department,
            actor=self.admin,
        )

        self.complaint.refresh_from_db()

        self.assertEqual(
            self.complaint.status,
            Complaint.Status.ASSIGNED,
        )
        self.assertEqual(self.complaint.assigned_to, self.admin)
        self.assertEqual(
            self.complaint.assigned_department,
            self.department,
        )

    def test_reassignment_preserves_in_progress_status(self):
        self.complaint.status = Complaint.Status.IN_PROGRESS
        self.complaint.save()

        new_department, created = Department.objects.get_or_create(
            name="IT Services"
        )

        assign_complaint(
            self.complaint,
            assigned_to=self.admin,
            department=new_department,
            actor=self.admin,
        )

        self.complaint.refresh_from_db()

        self.assertEqual(
            self.complaint.status,
            Complaint.Status.IN_PROGRESS,
        )
        self.assertEqual(
            self.complaint.assigned_department,
            new_department,
        )

    def test_assignment_rejected_for_submitted_complaint(self):
        self.complaint.status = Complaint.Status.SUBMITTED
        self.complaint.save()

        with self.assertRaises(InvalidAssignment):
            assign_complaint(
                self.complaint,
                assigned_to=self.admin,
                department=self.department,
                actor=self.admin,
            )

    def test_assignment_requires_admin_or_department(self):
        with self.assertRaises(InvalidAssignment):
            assign_complaint(
                self.complaint,
                actor=self.admin,
            )

    def test_non_admin_cannot_assign_complaint(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse(
                "complaints:admin_assign",
                args=[self.complaint.pk],
            ),
            {
                "assigned_to": self.admin.pk,
                "department": self.department.pk,
            },
        )

        self.assertEqual(response.status_code, 403)

        self.complaint.refresh_from_db()

        self.assertEqual(
            self.complaint.status,
            Complaint.Status.UNDER_REVIEW,
        )

    def test_admin_can_assign_complaint_through_view(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse(
                "complaints:admin_assign",
                args=[self.complaint.pk],
            ),
            {
                "assigned_to": self.admin.pk,
                "department": self.department.pk,
            },
        )

        self.assertEqual(response.status_code, 302)

        self.complaint.refresh_from_db()

        self.assertEqual(
            self.complaint.status,
            Complaint.Status.ASSIGNED,
        )
        self.assertEqual(self.complaint.assigned_to, self.admin)
        self.assertEqual(
            self.complaint.assigned_department,
            self.department,
        )
