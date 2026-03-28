# Stremet Hackathon - Steel Order Management System

A Django web application for managing steel manufacturing orders, tracking production stages, and providing real-time order status to customers.

## Features

- **Staff Dashboard** - Unified panel for administrators and manufacturers to create, search, and manage orders.
- **Manufacturing Flowchart Tracking** - Five-step production pipeline (Programming, Cutting, Forming, Joining, Delivery) with per-item status updates via AJAX.
- **Customer Portal** - Customers can look up their order by ID and view the current production status.
- **Role-Based Access** - User profiles with roles: Administrator, Customer, Manufacturer, Designer.
- **Order Management** - Full order lifecycle from creation through delivery, including file uploads, reference images, modification requests, and chat messages.

## Tech Stack

- **Backend:** Django 6.0 / Python 3.13
- **Database:** SQLite (development)
- **Frontend:** Django templates with static CSS

## Project Structure

```
my_django_setup/myproject/
├── manage.py
├── conftest.py              # Shared pytest fixtures
├── myproject/               # Settings package, root URL config, WSGI/ASGI
│   └── settings/
│       ├── base.py          # Shared settings
│       ├── local.py         # Default dev (DEBUG=True)
│       └── production.py    # Used when DJANGO_SETTINGS_ENV=production
├── home/                    # Core app: models, staff views, auth helpers
│   ├── services.py          # Order creation, chat, flowchart updates
│   ├── tests/
│   └── templates/home/
├── customer/                # Customer-facing app (order lookup)
│   ├── templates/customer/
│   └── static/css/
├── designer/                # Manufacturing plans, graph editor, steps
│   ├── services/            # Plan backfill, graph DAG validation/save
│   ├── tests/
│   └── static/designer/
├── manufacturer/            # Shop floor execution views
│   ├── services.py
│   └── static/manufacturer/
└── media/                   # Uploaded blueprints and reference images
```

Repository root also includes `pyproject.toml` (Ruff, pytest), `mypy.ini`, `.pre-commit-config.yaml`, and `.github/workflows/ci.yml`.

## Getting Started

### Prerequisites

- Python 3.13+

### Installation

1. Clone the repository:

   ```bash
   git clone <repository-url>
   cd Stremet-Hackathon
   ```

2. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # macOS / Linux
   source .venv/bin/activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Apply database migrations:

   ```bash
   cd my_django_setup/myproject
   python manage.py migrate
   ```

5. Create a superuser:

   ```bash
   python manage.py createsuperuser
   ```

6. Run the development server:

   ```bash
   python manage.py runserver
   ```

7. Open your browser at `http://127.0.0.1:8000/`.

### Development tooling (optional)

Install lint/test tools and enable git hooks:

```bash
pip install -r requirements-dev.txt
pre-commit install
```

Run checks locally:

```bash
ruff check my_django_setup/myproject
ruff format my_django_setup/myproject
cd my_django_setup/myproject && python manage.py check
pytest -q   # from repository root
```

## Configuration

By default, `DJANGO_SETTINGS_MODULE` is `myproject.settings`, which loads **local** development settings unless you opt into production.

| Variable | When | Purpose |
|----------|------|---------|
| `DJANGO_SETTINGS_ENV` | Production | Set to `production` to load `myproject.settings.production`. |
| `DJANGO_SECRET_KEY` | Production | **Required** in production; must be a strong secret. |
| `DJANGO_ALLOWED_HOSTS` | Production | Comma-separated hostnames (e.g. `example.com,www.example.com`). |

Local settings use a fixed dev `SECRET_KEY` and `DEBUG=True` (not for deployment).

## URL Routes

| URL | Description |
|-----|-------------|
| `/` | Landing dashboard |
| `/login/` | Staff login (`login` URL name) |
| `/logout/` | Logout (`logout` URL name) |
| `/dashboard/` | Unified staff panel |
| `/customer/` | Customer order lookup |
| `/designer/` | Designer manufacturing plans |
| `/manufacturer/` | Manufacturer execution views |
| `/admin/` | Django admin interface |
