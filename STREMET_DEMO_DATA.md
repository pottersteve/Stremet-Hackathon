# Stremet sample data (sheet metal production)

This project includes a Django management command that **removes only a fixed scope of sample rows** and **recreates** realistic content: B2B clients, sales orders, manufacturing plans (BOM, quality checks, dependencies, warehouse pickups), stock, chats, modification requests, and reference images.

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

Only rows that match this command’s **fixed identifiers** (everything else is left as-is):

| Scope | Rule |
|--------|------|
| Orders | `order_id` starts with **`SO-2026-90`** (block **SO-2026-9001** … **SO-2026-9018**). |
| Warehouse catalog | `ItemReservation.sku` in the built-in seed list (e.g. `SHE-DC01-2.0-ZE`, `TUB-S235-30X30X2`, …). |
| Clients | The eight procurement contact emails listed below. |
| Users | Usernames: `virtanen.mikko`, `nieminen.laura`, `koskinen.jukka`, `lehtonen.sanna`, `makinen.eero`, `rantanen.helena`, `lindstrom.noora`. |

**Important:** If you ever seeded with an older command that used different order IDs or SKUs, those old rows are **not** removed by this wipe. Clean them manually or use a fresh database.

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

Examples (all are removed on re-seed if still present):

- `SHE-DC01-2.0-ZE`, `SHE-304-1.5-2B`, `SHE-S355MC-3.0` — sheet  
- `TUB-S235-30X30X2` — tube  
- `HW-M6-A2-ASM01` — hardware kit  
- `POW-RAL7035-EP` — powder  

---

## Security

- Default password and fictional domains are for **local training and presentations** only.  
- Do not run against production without reviewing wipe scope and credentials.  
- Re-running the command only clears the scoped identifiers above.

---

## Implementation

- Command: [home/management/commands/seed_stremet_demo.py](my_django_setup/myproject/home/management/commands/seed_stremet_demo.py)  
- Pickup DAG sync: [designer/services/warehouse_sync.py](my_django_setup/myproject/designer/services/warehouse_sync.py)
