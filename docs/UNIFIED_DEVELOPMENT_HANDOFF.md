# CBA IMS — Unified Development Handoff & Architecture Guide

> **Document Version:** 4.0.0 (Unified Phase 4 Integration)  
> **Effective Date:** October 20, 2026  
> **Status:** Authoritative Multi-Device Development Baseline  
> **Canonical Repository:** `https://github.com/echo10000/cba_ims_backup.git` (Private Development & Backup)  
> **Canonical Branch:** `develop`  
> **Production Repository:** `https://github.com/echo10000/cba_ims.git` (Protected — Untouched)

---

## 1. Architectural Overview & Phase 4 Status

The CBA Asset & Inventory Management System (CBA IMS) previously underwent parallel development across separate "Staff" and "Student" sessions. As of Phase 4 (Checkpoint commit `413fd51`), both modules have been fully unified into a single coherent codebase.

### Integrated Portals
1. **Student Equipment Reservation Portal:**
   - **Public Landing (`/student/` and root `/`):** Frictionless, no-authentication-required interface for students to browse instructional equipment.
   - **Projector-First Equipment Catalog (`/student-reservations/`):** Dynamic schedule availability check prioritizes classroom LCD projectors and features them as primary equipment, while grouping audio/accessories secondarily and collapsing unavailable items.
   - **Request Submission & Tracking (`/student-reservations/request/`, `/student-reservations/lookup/`):** Two-step schedule flow with token-based lookup; masks student ID numbers and preserves student privacy.
   - **Physical ID Custody & Handover (`/student-reservations/manage/<pk>/`):** Property custodians approve reservations, allocate physical inventory items, and enforce fail-closed School ID custody validation (`release_equipment(..., *, id_deposited=False)`).

2. **Staff Operations Portal:**
   - **Staff Authentication (`/staff/` & `/accounts/login/`):** Dedicated staff login entry point isolated from student navigation.
   - **Staff Dashboard (`/dashboard/`):** Redesigned layout with operational queues (Guard Returns, Overdue Borrowings, Pending Reservations, Open Maintenance, Low Supplies), condition breakdown progress bars, and inventory distribution charts.
   - **Role-Based Access Control (RBAC):** Strict 4-role navigation and permissions:
     - `ADMIN / PROPERTY CUSTODIAN`: Full operational queue access, management tools, audit logs.
     - `DEAN / ASSISTANT DEAN`: Executive asset oversight, college-wide reports, disposal approvals.
     - `DEPARTMENT CHAIR`: Department-scoped inventory tracking and verification.
     - `FACULTY / BORROWER`: Personal equipment accountability and borrowing requests.
   - **Null-User Audit Robustness:** Activity log displays `"System"` cleanly when activity records have no associated user (`user=None`).

---

## 2. Setting Up on a New Windows Computer

Follow this exact step-by-step procedure to replicate the development environment on any secondary machine.

### Step 2.1 — Clone the Canonical Repository
Open PowerShell and clone the private repository into your preferred workspace directory:
```powershell
# Navigate to your preferred workspace root (e.g. $HOME\Desktop, $HOME\Projects, or C:\Projects):
Set-Location "$HOME\Desktop"
git clone https://github.com/echo10000/cba_ims_backup.git cba_ims
Set-Location "cba_ims"
git checkout develop
```

### Step 2.2 — Python Virtual Environment Setup
Ensure Python 3.12+ is installed, then create and activate an isolated virtual environment:
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Step 2.3 — Configure Device-Local Environment Variables
Create a local `.env` file in the project root. **Never commit this file or include production secrets.**

```ini
# CBA IMS — Local Device Configuration
DEBUG=True
SECRET_KEY=local-dev-placeholder-secret-change-for-your-device-key-38914
DB_ENGINE=django.db.backends.sqlite3
DB_NAME=local_dev_db.sqlite3
DATABASE_URL=
DB_SSLMODE=
TIME_ZONE=Asia/Manila
```

> [!CAUTION]
> Always verify that `DATABASE_URL` is empty. Never enter a hosted Neon PostgreSQL connection string into a local testing environment.

### Step 2.4 — Database Initialization & Migrations
Initialize the empty local database:
```powershell
.\venv\Scripts\python.exe manage.py check
.\venv\Scripts\python.exe manage.py migrate
```

### Step 2.5 — Fictional Test Account Fixtures
Create local test users programmatically or with `createsuperuser`. Do not use real institutional passwords or actual student numbers:
```powershell
# Interactive superuser creation:
.\venv\Scripts\python.exe manage.py createsuperuser --username test_admin --email admin@cba.edu
```

Or seed sample fictional equipment via a small local script:
- Create reservable `AssetCategory` (e.g. "Projectors", `is_reservable=True`).
- Create `EquipmentType` (e.g. "Classroom LCD Projector").
- Create an `Asset` (e.g. `PRJ-001`, `status=AVAILABLE`, `is_reservable=True`).

---

## 3. Local Development URLs

When running `python manage.py runserver 127.0.0.1:8000`:

| Component | URL | Notes |
| :--- | :--- | :--- |
| **Root (Student Redirect)** | `http://127.0.0.1:8000/` | Automatically redirects to `/student/` |
| **Student Portal Landing** | `http://127.0.0.1:8000/student/` | Public student hero & navigation |
| **Projector Catalog** | `http://127.0.0.1:8000/student-reservations/` | Live schedule availability & featured projector card |
| **Reservation Request** | `http://127.0.0.1:8000/student-reservations/request/` | Two-step schedule & details form |
| **Request Lookup** | `http://127.0.0.1:8000/student-reservations/lookup/` | Token-based tracking |
| **Staff Login** | `http://127.0.0.1:8000/staff/` | Dedicated staff login |
| **Staff Dashboard** | `http://127.0.0.1:8000/dashboard/` | Authenticated staff workspace & operational queues |
| **Custodian Queue** | `http://127.0.0.1:8000/student-reservations/manage/` | Custodian approval and release workflow |

---

## 4. Multi-Device Git Workflow

To prevent workspace conflicts, split histories, or lost commits across devices, follow this strict protocol:

### When Starting Work on Any Machine:
1. Ensure your working tree is clean (`git status`).
2. Pull the latest commits from the private canonical repository:
   ```powershell
   git checkout develop
   git pull --ff-only origin develop
   ```

### When Making Changes:
1. Make targeted, focused modifications.
2. Run Django checks and isolated test suites:
   ```powershell
   .\venv\Scripts\python.exe manage.py check
   .\venv\Scripts\python.exe manage.py test apps.student_reservations apps.accounts
   ```
3. Stage only source code and test files:
   ```powershell
   git add <modified-files>
   git commit -m "feat(module): description of changes"
   ```

### When Finishing Work on a Machine:
1. Never leave unpushed commits when switching devices:
   ```powershell
   git push origin develop
   ```
2. Verify with `git status` that your branch is up to date with `origin/develop`.
3. If uncommitted work cannot be pushed yet, create a local Git bundle or patch file in a designated backup folder outside the repository (e.g., `$HOME\Desktop\CBA_IMS_Backups\` or a secure flash drive) as an emergency safety net.

---

## 5. Security & Safety Rules

- **Zero Database Commits:** SQLite database files (`*.sqlite3`) are strictly gitignored. Never add or commit database files.
- **Zero Real Credentials:** Never commit student names, real student ID numbers, institutional phone numbers, email passwords, or API keys.
- **Production Isolation:**
  - Public repository (`https://github.com/echo10000/cba_ims.git`) is reserved for validated release tags. Do not push experimental work or test branches to it.
  - Vercel and Neon production instances are strictly protected and must never be targeted by local runserver commands or ad-hoc seed scripts.

---

## 6. Known Incomplete Work & Next Milestones

1. **Genuine 2-Client Playwright/Selenium Tests:** Two-client simultaneous booking acceptance tests are prepared but should be executed in an automated test harness.
2. **Bulk Equipment Return Queue:** Security guard return workflow currently handles individual reservations; batch-processing returns from guards during evening hours can be streamlined.
3. **PWA Offline Service Worker:** Manifests for student and staff portals are distinct; service worker caching strategy for student schedule presets can be enhanced.
