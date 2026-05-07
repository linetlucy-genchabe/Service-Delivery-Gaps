# Kenya CHA Dashboard

Internal community health analytics platform for Kenya county health systems.
Tracks CHW/CHP performance, supervision coverage, and health indicator gaps.

---

## Prerequisites

- Python 3.10+
- PostgreSQL 14+
- pip

---

## Setup

### 1. Clone / extract the project

```bash
cd /path/to/your/projects
# place the cha_dashboard folder here
cd cha_dashboard
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv
source venv/bin/activate        # Linux / Mac
# venv\Scripts\activate          # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

```bash
cp .env.example .env
# Edit .env with your actual database credentials and a secret key
```

Generate a secret key:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 5. Create the PostgreSQL database

```bash
psql -U postgres
CREATE DATABASE cha_dashboard;
\q
```

### 6. Run migrations

```bash
python manage.py migrate
```

### 7. Create the superuser (you)

```bash
python manage.py createsuperuser
```

### 8. Create manager accounts (for data uploaders)

Manager accounts need `is_staff=True` to access the upload page.
Create them via Django admin at `/admin/` or:

```bash
python manage.py shell
>>> from django.contrib.auth.models import User
>>> u = User.objects.create_user('manager_name', password='password123')
>>> u.is_staff = True
>>> u.save()
```

### 9. Run the development server

```bash
python manage.py runserver
```

Open: http://127.0.0.1:8000/

---

## Usage

### Uploading Data

1. Sign in as superuser or staff account
2. Click **Upload Data** in the navbar
3. Select **Period Type**: Monthly or Weekly
4. Select **Month** and **Year**
5. For weekly uploads: select the **Week Start Date** (the Monday of that week)
6. Upload both the **CHW Detail File** and **Supervision File** together
7. Click **Upload Both Files**

> ⚠️ Each upload is stored independently. Uploading April Week 1 will never overwrite April Week 2 or April Monthly data.

### Viewing the Dashboard

- Anyone with a login can view the dashboard (read-only)
- Use the **Reporting Period** dropdown to select which dataset to view
- Filter by **County → Sub-County → Community Health Unit** (cascading)
- Hover over any card's **"View definition"** link to see what the indicator measures

### Downloading Data

Each drill-down table has a **⬇ Download CSV** button that exports the currently filtered data.

---

## File Structure

```
cha_dashboard/
├── cha_dashboard/
│   ├── settings.py        # Django settings
│   ├── urls.py            # Root URL config
│   └── wsgi.py
├── dashboard/
│   ├── models.py          # Database models (UploadBatch, CHWRecord, SupervisionRecord)
│   ├── views.py           # All views (login, dashboard, upload, APIs, downloads)
│   ├── urls.py            # App URL patterns
│   ├── forms.py           # Upload & login forms
│   ├── parsers.py         # Excel parsing + indicator calculations
│   ├── admin.py           # Django admin registration
│   ├── migrations/        # Database migrations
│   ├── templates/dashboard/
│   │   ├── base.html      # Shared layout (navbar, footer)
│   │   ├── login.html     # Login page
│   │   ├── dashboard.html # Main dashboard
│   │   └── upload.html    # Upload page
│   └── static/dashboard/
│       ├── css/styles.css # All styles (white/blue/orange/purple palette)
│       └── js/dashboard.js # Tabs, drill-down tables, definition modal
├── .env.example
├── manage.py
└── requirements.txt
```

---

## Indicator Definitions

| Indicator | Definition |
|---|---|
| Active CHPs | CHPs with Active = "Yes" in eCHIS |
| Supervision Rate | % of active CHPs with ≥1 supervision visit this period |
| Unsupervised CHPs | Active CHPs with 0 supervision visits |
| Same-Day Flags | CHUs where ≥5 CHPs were supervised on the same date |
| Low Performers (Monthly) | Active CHPs with <50 HH visits |
| Low Performers (Weekly) | Active CHPs with <12 HH visits |
| ANC Gap | Pregnancies Registered − Pregnancies Visited |
| FP Refill Gap | FP Needing Refill − FP Refilled |
| IZ Fully Immunized Rate | IZ Fully Immunized ÷ IZ Assessed (9–23mo) × 100 |
| Facility Delivery Rate | Facility Deliveries ÷ Total Deliveries × 100 |
| MAM/SAM Referral Rate | MAM/SAM Referred ÷ MAM/SAM Total × 100 |

---

## Production Notes

- Set `DEBUG=False` in `.env` for production
- Set `ALLOWED_HOSTS` to your actual domain
- Run `python manage.py collectstatic` for static files
- Use gunicorn + nginx for serving
- Set up regular PostgreSQL backups
