from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("complaints", "0003_complaint_status_rejected_closed"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Rename changed_at -> updated_at (data-preserving column rename)
        migrations.RenameField(
            model_name="complainthistory",
            old_name="changed_at",
            new_name="updated_at",
        ),
        # Rename changed_by -> updated_by (data-preserving column rename)
        migrations.RenameField(
            model_name="complainthistory",
            old_name="changed_by",
            new_name="updated_by",
        ),
        # Add update_details; existing rows get an empty string
        migrations.AddField(
            model_name="complainthistory",
            name="update_details",
            field=models.TextField(blank=True, default=""),
            preserve_default=False,
        ),
        # Update Meta.ordering to reflect the renamed field
        migrations.AlterModelOptions(
            name="complainthistory",
            options={"ordering": ["updated_at"], "verbose_name_plural": "complaint history"},
        ),
    ]
