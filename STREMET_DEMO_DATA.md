# Stremet sample data (sheet metal production)

This project includes a Django management command that **flushes the entire database** (all application data Django manages, equivalent to `python manage.py flush --no-input`), runs **`migrate`** to restore content types and permissions, recreates warehouse storage slots if needed, then loads realistic sample content: B2B clients, sales orders, manufacturing plans (BOM, quality checks, dependencies, warehouse pickups), stock, chats, modification requests, and reference images.

**Context:** Data is written to resemble Finnish sheet metal subcontracting (laser, bending, welding, punching, painting, assembly) and industrial customers (elevators, HVAC, machinery, energy, transport, healthcare, construction, lighting). Company and person names are **fictional**; email domains are invented for training and **must not** be used to send real mail.

**Order status** values in the database (`melting`, `rolling`, etc.) are legacy stage keys. The realistic story is in **admin notes**, **dimensions**, **material grades**, **manufacturing steps**, and **plans**.

---

## Prerequisites

- Python environment with dependencies from [requirements.txt](requirements.txt).
- Migrations applied.

```bash
cd my_django_setup/myproject
python manage.py migrate
```

---

## Generate or refresh sample data

```bash
cd my_django_setup/myproject
python manage.py seed_stremet_demo
```

### What gets removed

**Everything** in the database that Django’s `flush` clears: all users (including superusers), sessions, orders, plans, warehouse rows, admin log, and other app tables. The schema and migration history stay; **`migrate`** is run immediately after flush so `django_content_type`, `auth_permission`, and related system rows are repopulated.

**Warning:** Do not run this command against any database that holds data you need to keep. Use a dedicated dev or demo database only.

### Password

- Set **`STREMET_SEED_PASSWORD`** in the environment for a custom password.
- If unset, the default is **`StremetTrain2026!`** (local/training use only — not for production).

---

## Users (staff login: `/login/`)

| Username | Role | Typical use |
|----------|------|-------------|
| `virtanen.mikko` | Administrator | Admin panel, client directory, staff dashboard, quote flow |
| `nieminen.laura` | Designer | `/designer/` — plans, steps, BOM, graph |
| `koskinen.jukka` | Manufacturer | `/manufacturer/` — production queue and steps |
| `lehtonen.sanna` | Warehouse | `/warehouse/` — stock and pickups |
| `makinen.eero` | Customer | `/request-quote/` — matches **Pohjan Lift Components Oy** contact email |
| `rantanen.helena` | Customer | Matches **Salo HVAC Engineering Oy** |
| `lindstrom.noora` | Customer | Matches **MedPanel Device Housings Oy** |

Staff addresses use `@stremet.fi`; customer logins use the same address as the corresponding **Client** row (quote portal `get_or_create` by email).

---

## Sample clients (CRM)

| Contact email | Company |
|----------------|---------|
| eero.makinen@pohjanlift.fi | Pohjan Lift Components Oy |
| helena.rantanen@salohvac.fi | Salo HVAC Engineering Oy |
| antti.korhonen@koneturva.fi | Koneturva Guard Systems Oy |
| liisa.hamalainen@latauskaari.fi | Latauskaari EV Structures Oy |
| noora.lindstrom@medpanel.fi | MedPanel Device Housings Oy |
| markus.salo@tuuli-inverter.fi | Tuuli-Inverter Cabinets Oy |
| kaisa.toivonen@julkisivukiinnike.fi | Julkisivukiinnike Oy |
| petri.heikkinen@logistiikkakori.fi | Logistiikkakori Assembly Oy |

---

## Sample sales orders (customer lookup: `/customer/`)

Eighteen orders: **`SO-2026-9001`** through **`SO-2026-9018`**.

Suggested IDs to try:

- **SO-2026-9001** — Approved plan, chat thread, reference image, modification request  
- **SO-2026-9003** — Mixed order status and manufacturing progress  
- **SO-2026-9006** — Draft manufacturing plan  
- **SO-2026-9012** — Another draft plan  

Customer-facing progress uses **manufacturing steps** on the plan (`customer_order_progress_context` in [home/services.py](my_django_setup/myproject/home/services.py)).

---

## Warehouse material SKUs (seed catalog)

Examples (inserted after each full flush):

- `SHE-DC01-2.0-ZE`, `SHE-304-1.5-2B`, `SHE-S355MC-3.0` — sheet  
- `TUB-S235-30X30X2` — tube  
- `HW-M6-A2-ASM01` — hardware kit  
- `POW-RAL7035-EP` — powder  

---

## Security

- Default password and fictional domains are for **local training and presentations** only.  
- **Never** run `seed_stremet_demo` against production or shared databases: it **wipes all data**.  
- After a run you must **create a new superuser** if you need Django admin access (`createsuperuser`), because existing admin accounts are deleted by flush.

---

## Implementation

- Command: [home/management/commands/seed_stremet_demo.py](my_django_setup/myproject/home/management/commands/seed_stremet_demo.py)  
- Pickup DAG sync: [designer/services/warehouse_sync.py](my_django_setup/myproject/designer/services/warehouse_sync.py)
