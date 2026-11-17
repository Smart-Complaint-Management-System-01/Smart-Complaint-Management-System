"""Settings for running the automated test suite and coverage reports.

Uses SQLite so tests run without a MySQL server. Run with:
    python manage.py test --settings=config.test_settings
or  pytest   (pytest.ini points here)
"""
from .settings import *  # noqa: F401,F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "test_db.sqlite3",
        "TEST": {"NAME": BASE_DIR / "test_db.sqlite3"},
        "OPTIONS": {"timeout": 30},
    }
}
