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

## Automated UI tour (Playwright)

The script [`scripts/stremet_ui_tour.py`](scripts/stremet_ui_tour.py) opens a **visible** Chromium window and drives the same flows people use in production: quote request, portal tracking and chat, support with **Suggest AI Reply** (local GPT4All), designer plan and BOM, warehouse pickup, manufacturer step completion, then checking status again as the customer.

By default, automated clicks and field fills wait **250 ms** after each action (`--action-delay-ms 250`). Playwright `slow_mo` defaults to **0** for normal speed. Between workflow phases the script waits for **Enter** so you can stop and look; use `--no-pause` to run straight through with only that 250 ms pacing between beats.

### Prerequisites

- **Virtual environment** — Same venv for Django, `gpt4all`, and Playwright.

  ```bash
  python -m venv .venv
  # Windows
  .venv\Scripts\activate
  # macOS / Linux
  source .venv/bin/activate
  ```

- **Packages**

  ```bash
  pip install -r requirements.txt -r requirements-dev.txt
  python -m playwright install chromium
  ```

- **GPT4All** — Django preloads the model when each `manage.py` process runs (`migrate`, `seed_stremet_demo`, `runserver`), which can take several minutes on a cold machine. The script waits up to **900 s** for HTTP after `runserver` starts unless you set `--server-ready-timeout` higher.

### Run (repository root, venv active)

```bash
python scripts/stremet_ui_tour.py
```

This runs `migrate`, `seed_stremet_demo`, starts `runserver` on `127.0.0.1:8000`, waits for `/`, then runs the walkthrough.

### Accounts and passwords

Sample users and wipe rules: [`STREMET_DEMO_DATA.md`](STREMET_DEMO_DATA.md). Default password is `StremetTrain2026!` unless **`STREMET_SEED_PASSWORD`** is set when you run the script (and when seeding).

```bash
python scripts/stremet_ui_tour.py --password "YourSeedPassword"
```

### Useful options

| Flag | Purpose |
|------|---------|
| `--no-pause` | No Enter between phases; only `--action-delay-ms` between beats. |
| `--no-server` | Do not start `runserver`; use a running instance (`--base-url` if needed). |
| `--skip-migrate` / `--skip-seed` | Skip database steps (debugging). |
| `--order-id SO-2026-10001` | Fixed order id (default `SO-2026-<unix_ts>`). |
| `--server-ready-timeout 1200` | Seconds to wait for HTTP after `runserver` (GPT4All startup). |
| `--ai-timeout-sec 180` | Max wait for streamed AI text in support reply box. |
| `--action-delay-ms 250` | Pause after each automated UI action (default **250** ms). |
| `--slow-mo` | Extra Playwright delay per action (default **0**). |

`python scripts/stremet_ui_tour.py --help` lists everything.

### Troubleshooting

- **`seed_stremet_demo` + protected foreign key** — Often a previous incomplete run left BOM rows pointing at catalog lines the seed command tries to delete. Restore from backup or reset `db.sqlite3`, then `migrate` and `seed_stremet_demo` again. See `STREMET_DEMO_DATA.md`.
- **AI reply stays empty** — Ensure `gpt4all` works in this venv and the model has finished loading. The script uses a short fallback message if the stream does not finish within `--ai-timeout-sec`.
- **Chromium missing** — Run `python -m playwright install chromium` in the same venv as the script.

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
