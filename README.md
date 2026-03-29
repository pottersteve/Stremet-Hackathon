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

## Pitch / demo tour (Playwright)

The script [`scripts/stremet_pitch_tour.py`](scripts/stremet_pitch_tour.py) is a **headed** browser automation used for product pitches. It prepares the database, starts Django, checks that the app responds, then walks through the main user journey in order:

1. **Customer** — log in, submit a quote request, open the customer portal, track the order, send a support chat message.
2. **Support (admin)** — open the support hub, use **Suggest AI Reply** (local GPT4All), send the reply.
3. **Designer** — add a manufacturing step, attach BOM material from seeded catalog, add a quality check, set plan to **Ready**, save.
4. **Warehouse** — complete the pickup for that order.
5. **Manufacturer** — complete the manufacturing step and quality fields.
6. **Customer** — track the same order again to show progress.

Between major beats, the script pauses on **Press Enter** so a presenter can talk (default). Use `--no-pause` for unattended dry runs (short automatic delays instead).

### Prerequisites

- **Virtual environment** — Use the same venv for Django, `gpt4all`, and Playwright so imports and binaries match.

  ```bash
  python -m venv .venv
  # Windows
  .venv\Scripts\activate
  # macOS / Linux
  source .venv/bin/activate
  ```

- **Packages** — App dependencies plus dev tools (includes Playwright):

  ```bash
  pip install -r requirements.txt -r requirements-dev.txt
  python -m playwright install chromium
  ```

- **GPT4All** — Listed in `requirements.txt`. On first run, Django **preloads** the model when each `manage.py` process starts (`migrate`, `seed_stremet_demo`, then `runserver`). That can take several minutes per step on a cold machine. The script waits up to **15 minutes** (900 s) for HTTP after starting `runserver`; increase with `--server-ready-timeout` if needed.

### One-command demo (from repository root)

With the venv **activated**:

```bash
python scripts/stremet_pitch_tour.py
```

This runs `migrate`, `seed_stremet_demo`, starts `runserver` on `127.0.0.1:8000`, waits until `/` returns HTTP, opens Chromium, and runs the tour.

### Demo users and passwords

Seeded accounts and wipe rules are documented in [`STREMET_DEMO_DATA.md`](STREMET_DEMO_DATA.md). Default password for seed users is `StremetTrain2026!` unless you set **`STREMET_SEED_PASSWORD`** in the environment before running the script (and before seeding).

You can pass a password explicitly:

```bash
python scripts/stremet_pitch_tour.py --password "YourSeedPassword"
```

### Useful options

| Flag | Purpose |
|------|---------|
| `--no-pause` | No Enter key between story beats; fixed short delays only. |
| `--no-server` | Do not start `runserver`; use an already running app. Set `--base-url` if not `http://127.0.0.1:8000`. |
| `--skip-migrate` / `--skip-seed` | Skip database steps (for debugging). |
| `--order-id SO-2026-DEMO-001` | Fixed quote id instead of `SO-2026-DEMO-<timestamp>`. |
| `--server-ready-timeout 1200` | Seconds to wait for the site after `runserver` starts (GPT4All preload). |
| `--ai-timeout-sec 180` | How long to wait for the AI reply stream in the support UI. |
| `--action-delay-ms 1000` | Extra pause after each automated click/fill (default 1000). |
| `--slow-mo 350` | Playwright `slow_mo` in milliseconds (default 350). |

Run `python scripts/stremet_pitch_tour.py --help` for the full list.

### Troubleshooting

- **`seed_stremet_demo` fails with a protected foreign key** — Often caused by a **partial** tour that left extra BOM rows on a demo order. Use a fresh database (`db.sqlite3` removed after backup, then `migrate` + `seed`), or clean up manually. See wipe scope in `STREMET_DEMO_DATA.md`.
- **AI button never fills the reply** — Confirm `gpt4all` works in this venv and that the model finished loading (watch the terminal where `runserver` runs). The tour falls back to placeholder reply text if the stream does not appear within `--ai-timeout-sec`.
- **Playwright cannot find Chromium** — Run `python -m playwright install chromium` inside the **same** venv you use for the script.

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
