import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("complaints", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # --- Department ---
        migrations.CreateModel(
            name="Department",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, unique=True)),
            ],
            options={"ordering": ["name"]},
        ),

        # --- Complaint: Sprint 2 fields ---
        migrations.AddField(
            model_name="complaint",
            name="assigned_to",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="assigned_complaints",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="complaint",
            name="assigned_department",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="complaints",
                to="complaints.department",
            ),
        ),
        migrations.AddField(
            model_name="complaint",
            name="resolution_details",
            field=models.TextField(blank=True, default=""),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="complaint",
            name="resolved_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        # Sprint 2 status choices (REJECTED, CLOSED) + NFR-01 indexes
        migrations.AlterField(
            model_name="complaint",
            name="status",
            field=models.CharField(
                choices=[
                    ("SUBMITTED", "Submitted"),
                    ("UNDER_REVIEW", "Under Review"),
                    ("ASSIGNED", "Assigned"),
                    ("IN_PROGRESS", "In Progress"),
                    ("RESOLVED", "Resolved"),
                    ("REJECTED", "Rejected"),
                    ("CLOSED", "Closed"),
                ],
                db_index=True,
                default="SUBMITTED",
                max_length=20,
            ),
        ),
        migrations.AlterModelOptions(
            name="complaint",
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="complaint",
            index=models.Index(fields=["category"], name="complaints__categor_8115a1_idx"),
        ),
        migrations.AddIndex(
            model_name="complaint",
            index=models.Index(fields=["created_at"], name="complaints__created_805464_idx"),
        ),

        # --- ComplaintHistory ---
        migrations.CreateModel(
            name="ComplaintHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("previous_status", models.CharField(
                    blank=True,
                    choices=[
                        ("SUBMITTED", "Submitted"),
                        ("UNDER_REVIEW", "Under Review"),
                        ("ASSIGNED", "Assigned"),
                        ("IN_PROGRESS", "In Progress"),
                        ("RESOLVED", "Resolved"),
                        ("REJECTED", "Rejected"),
                        ("CLOSED", "Closed"),
                    ],
                    max_length=20,
                )),
                ("new_status", models.CharField(
                    choices=[
                        ("SUBMITTED", "Submitted"),
                        ("UNDER_REVIEW", "Under Review"),
                        ("ASSIGNED", "Assigned"),
                        ("IN_PROGRESS", "In Progress"),
                        ("RESOLVED", "Resolved"),
                        ("REJECTED", "Rejected"),
                        ("CLOSED", "Closed"),
                    ],
                    max_length=20,
                )),
                ("update_details", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("complaint", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="history",
                    to="complaints.complaint",
                )),
                ("updated_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="complaint_updates",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "verbose_name_plural": "complaint history",
                "ordering": ["created_at", "pk"],
            },
        ),

        # --- Notification ---
        migrations.CreateModel(
            name="Notification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("message", models.CharField(max_length=255)),
                ("is_read", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("complaint", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="notifications",
                    to="complaints.complaint",
                )),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="notifications",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"ordering": ["-created_at", "-pk"]},
        ),
    ]
