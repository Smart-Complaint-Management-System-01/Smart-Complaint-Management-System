# Smart Complaint Management System

A web application where users lodge complaints and track their resolution, and administrators review, assign, update and resolve them.

**Stack:** Python, Django (MVT), MySQL, Django ORM, HTML5/CSS/JavaScript, Git/GitHub

## Prerequisites

- Python 3.10 or newer (3.12 recommended)
- MySQL Server 8.x, running locally
- Git

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/Smart-Complaint-Management-System-01/Smart-Complaint-Management-System.git
cd Smart-Complaint-Management-System
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

If `mysqlclient` fails to install, use PyMySQL instead:

```bash
pip install PyMySQL
```

Then add these two lines at the top of `config/__init__.py`:

```python
import pymysql
pymysql.install_as_MySQLdb()
```

Do not commit that change unless the whole team agrees to switch.

### 4. Create the database

Open the MySQL shell and run:

```sql
CREATE DATABASE complaint_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Each team member uses their own local database.

### 5. Configure environment variables

```bash
cp .env.example .env            # Windows: copy .env.example .env
```

Edit `.env` and set your own MySQL password:

```
DJANGO_SECRET_KEY=change-me
DJANGO_DEBUG=True
DB_NAME=complaint_db
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_HOST=127.0.0.1
DB_PORT=3306
```

`.env` is git-ignored. Never commit it.

### 6. Apply migrations

```bash
python manage.py migrate
```

This includes the Sprint 2 migration `0002_sprint2_models` (departments, complaint history, notifications, assignment and resolution fields).

### 7. Load the default departments

```bash
python manage.py seed_departments
```

Safe to run more than once. Departments are needed for complaint assignment (FR-09).

### 8. Create an administrator account

```bash
python manage.py createsuperuser
```

Superusers automatically get the `ADMIN` role. You can log in with the **email** you enter here.

### 9. Run the server

```bash
python manage.py runserver
```

| URL | Purpose |
|---|---|
| http://127.0.0.1:8000/ | Home page |
| http://127.0.0.1:8000/register/ | User registration |
| http://127.0.0.1:8000/login/ | Login |
| http://127.0.0.1:8000/complaints/ | My complaints (users) |
| http://127.0.0.1:8000/complaints/\<complaint_id\>/ | Complaint details and status history (owner only) |
| http://127.0.0.1:8000/notifications/ | Status-change notifications (users) |
| http://127.0.0.1:8000/admin/complaints/ | Complaint management, search and filtering (administrators) |
| http://127.0.0.1:8000/admin/complaints/\<id\>/ | Admin complaint detail: assign, update, change status, resolve |
| http://127.0.0.1:8000/django-admin/ | Django's built-in admin site |

## Running tests

```bash
python manage.py test
```

Django creates a temporary `test_complaint_db` database. Your MySQL user needs permission to create databases:

```sql
GRANT ALL PRIVILEGES ON *.* TO 'your_user'@'localhost';
```

## Verifying data persistence (NFR-03)

1. Run `python manage.py runserver`, log in, and submit a complaint.
2. Stop the server with `Ctrl+C`.
3. Check the data is still in MySQL:
```bash
   python manage.py shell -c "from complaints.models import Complaint; print(list(Complaint.objects.values_list('complaint_id','title')))"
```
4. Start the server again. The complaint is still listed under **My Complaints**.

## Password security (NFR-09)

- Passwords are never stored in plaintext. Django stores only a salted, one-way **PBKDF2-SHA256** hash (`pbkdf2_sha256$...`) in the `password` column.
- Every user gets a different random salt, so two users with the same password have different hashes.
- Passwords must be at least 8 characters and pass Django's common-password, numeric-only and similarity validators.
- Passwords are never echoed back in responses or written to logs.
- Configured in `config/settings.py` (`PASSWORD_HASHERS`, `AUTH_PASSWORD_VALIDATORS`) and verified by `accounts/tests/test_password_security.py`.

## Performance and concurrency (NFR-01, NFR-02)

- Test NFR-02 with at least 100 distinct authenticated users against a local test database and a WSGI server. The helper below creates 100 normal user accounts and a private credentials CSV. It only operates against a local database and requires explicit confirmation:

```powershell
$env:DJANGO_DEBUG="True"
python manage.py seed_load_test_users --confirm-local --count 100
```

Start the application in another terminal. Install project dependencies first if Waitress is not present:

```powershell
python -m pip install -r requirements.txt
$env:DJANGO_DEBUG="False"
waitress-serve --threads=100 --listen=127.0.0.1:8000 config.wsgi:application
```

Run the load against a user-only route with each account logged in independently:

```powershell
python performance/load_test.py --url http://127.0.0.1:8000/complaints/ --users-file performance/test-users.csv
```

The test synchronizes 100 authenticated clients before measurement, then issues 1,000 requests by default. It records the authenticated-client count, completed/successful/failed requests, latency median/p95/maximum, throughput, status counts and slow requests to a timestamped JSON file under `performance/results/`. It exits nonzero if any authentication or request fails, fewer than 100 clients authenticate, or any request reaches the configured 3-second latency threshold. Override request count, concurrency, threshold or report location with `--requests`, `--concurrency`, `--threshold` or `--output`. The generated credentials and reports are git-ignored; keep credentials private. After testing, stop the server and remove the temporary users and credentials file:

```powershell
python manage.py seed_load_test_users --confirm-local --cleanup
```

Run against representative local data and hardware; a development test does not guarantee production capacity.

## Error recovery (NFR-04)

- Complaint creation runs in a single database transaction. If saving fails, nothing is stored and the user sees a clear message with their input kept.
- A one-time token on the lodge form prevents duplicates from double clicks, refreshes or back-button resubmits.
- Friendly 404 and 500 pages are provided.

## Project structure

```
config/          Project settings, root URLs, response-time middleware
accounts/        Custom User model (roles), registration, login, role decorators
complaints/      Complaint, Department, ComplaintHistory and Notification models;
                 services (status workflow, assignment, updates, resolution);
                 search/filter module; notifications; management commands
templates/       base.html, home.html, 403/404/500, partials/, accounts/, complaints/
                 (complaints/partials/ holds the admin detail sections)
static/          css/styles.css, js/main.js
performance/     load_test.py for the concurrent-user test
```

## Roles

| Role | Can do |
|---|---|
| `USER` (default on registration) | Register, log in, lodge complaints, view own complaints with status history, add information to an open complaint, read notifications |
| `ADMIN` | View all complaints, search and filter them, assign to an administrator or department, add updates, move a complaint along the status workflow, record the resolution |

Complaint status workflow: **Submitted → Under Review → Assigned → In Progress → Resolved**, one step at a time.

- **Assigned** is set by assigning the complaint (from Under Review). Reassignment later keeps the current status and is logged.
- **Resolved** can only be set by recording resolution details. The generic "Move to" button never resolves a complaint.
- Every status change, assignment, update and resolution writes a history entry (who, what, when).
- The complaint owner gets an in-app notification on every status change. Email is out of scope.

To promote an existing user to administrator, open `/django-admin/`, edit the user, and set **Role** to `Administrator`.

## Team workflow

**Branches:** one branch per issue, named `feature/<ID>-<short-name>`, for example `feature/FR-06-complaint-history`.

**Commit messages:** `type(scope): summary (ID)`, plus a `Refs #<issue>` line in the body.

```
feat(complaints): add Department, ComplaintHistory and Notification models (FR-06)

Refs #7
```

Types: `feat`, `fix`, `test`, `docs`, `style`, `chore`, `refactor`.

**Before every push:**

```bash
git pull --rebase origin main
python manage.py test
git push -u origin <your-branch>
```

**Pull requests:** put `Closes #<issue>` in the description and get one teammate's review before merging.

### Ground rules

- Only the person who changes `models.py` fields creates migrations. Tell the team first, and commit the migration file with the model change.
- After pulling someone's model change, run `python manage.py migrate`.
- If `urls.py`, `views.py` or `services.py` conflicts, keep both sides' lines.
- The admin complaint page is split into partials under `templates/complaints/partials/`. Edit only the partial for your feature.
- With `LoginRequiredMiddleware` enabled (NFR-07), every new page requires login by default. Mark public pages with `@login_not_required`.
- Never commit `.env`, `venv/`, or `db.sqlite3`.

## Sprint 1 scope

FR-01 User Registration · FR-02 User Authentication · FR-03 Role-Based Access · FR-04 Lodge Complaint · FR-05 View Complaint Status · FR-08 Admin Complaint Management · NFR-03 Data Persistence · NFR-05 Usability · NFR-06 Validation Feedback · NFR-07 Authentication Security · NFR-08 Authorization · NFR-10 Session Security

## Sprint 2 scope

FR-06 Complaint History · FR-07 Complaint Update · FR-09 Complaint Assignment · FR-10 Complaint Resolution · FR-11 Complaint Search and Filtering · FR-12 Complaint Notifications · NFR-01 Response Time · NFR-02 Concurrent Users · NFR-04 Error Recovery · NFR-09 Password Protection