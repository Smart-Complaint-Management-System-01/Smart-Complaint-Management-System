from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("complaints", "0002_complaint_history"),
    ]

    operations = [
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
        migrations.AlterField(
            model_name="complainthistory",
            name="new_status",
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
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="complainthistory",
            name="previous_status",
            field=models.CharField(
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
                null=True,
            ),
        ),
    ]
