from django.db import migrations


def seed_departments(apps, schema_editor):
    Department = apps.get_model("complaints", "Department")

    departments = [
        "IT Services",
        "Hostel",
        "Academics",
        "Infrastructure",
        "Finance",
    ]

    for name in departments:
        Department.objects.get_or_create(name=name)


def remove_departments(apps, schema_editor):
    Department = apps.get_model("complaints", "Department")

    Department.objects.filter(
        name__in=[
            "IT Services",
            "Hostel",
            "Academics",
            "Infrastructure",
            "Finance",
        ]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("complaints", "0003_submission_token"),
    ]

    operations = [
        migrations.RunPython(seed_departments, remove_departments),
    ]