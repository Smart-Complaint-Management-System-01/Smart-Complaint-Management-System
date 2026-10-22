# Smart Complaint Management System

A web application where users lodge complaints and track their resolution, and administrators review and manage them.

**Stack:** Python, Django (MVT), MySQL, Django ORM, HTML5/CSS/JavaScript, Git/GitHub

## Prerequisites

- Python 3.10 or newer (3.12 recommended)
- MySQL Server 8.x, running locally
- Git

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/Smart-Complaint-Management-System-01/Smart-Complaint-Management-System.git
cd Smart-Complaint-Management-System-01
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

### 7. Create an administrator account

```bash
python manage.py createsuperuser
```

Superusers automatically get the `ADMIN` role. You can log in with the **email** you enter here.

### 8. Run the server

```bash
python manage.py runserver
```

| URL | Purpose |
|---|---|
| http://127.0.0.1:8000/ | Home page |
| http://127.0.0.1:8000/register/ | User registration |
| http://127.0.0.1:8000/login/ | Login |
| http://127.0.0.1:8000/complaints/ | My complaints (users) |
| http://127.0.0.1:8000/admin/complaints/ | Complaint management (administrators) |
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

## Project structure

```
config/          Project settings, root URLs, placeholder view
accounts/        Custom User model (roles), registration, login, role decorators
complaints/      Complaint model, lodge/view views, admin management, status workflow
templates/       base.html, home.html, partials/, accounts/, complaints/
static/          css/style.css, js/main.js
```

## Roles

| Role | Can do |
|---|---|
| `USER` (default on registration) | Register, log in, lodge complaints, view own complaints and their status |
| `ADMIN` | View all complaints, open details, move a complaint along the status workflow |

Complaint status workflow: **Submitted → Under Review → Assigned → In Progress → Resolved**, one step at a time.

To promote an existing user to administrator, open `/django-admin/`, edit the user, and set **Role** to `Administrator`.

## Team workflow

**Branches:** one branch per issue, named `feature/<ID>-<short-name>`, for example `feature/FR-01-user-registration`.

**Commit messages:** `type(scope): summary (ID)`, plus a `Refs #<issue>` line in the body.

```
feat(accounts): add RegistrationForm with validation (FR-01)

Refs #1
```

Types: `feat`, `fix`, `test`, `docs`, `style`, `chore`.

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
- If `urls.py` conflicts, keep both sides' lines.
- With `LoginRequiredMiddleware` enabled (NFR-07), every new page requires login by default. Mark public pages with `@login_not_required`.
- Never commit `.env`, `venv/`, or `db.sqlite3`.

## Sprint 1 scope

FR-01 User Registration · FR-02 User Authentication · FR-03 Role-Based Access · FR-04 Lodge Complaint · FR-05 View Complaint Status · FR-08 Admin Complaint Management · NFR-03 Data Persistence · NFR-05 Usability · NFR-06 Validation Feedback · NFR-07 Authentication Security · NFR-08 Authorization · NFR-10 Session Security
