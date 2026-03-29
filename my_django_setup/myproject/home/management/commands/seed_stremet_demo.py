"""
Flush the entire database, then create realistic Stremet-style sheet metal data.

Destructive: removes all rows Django manages (same as ``manage.py flush``), then
runs ``migrate`` to restore content types and permissions, re-seeds warehouse
slots if needed, and inserts sample users, orders, and related records.
"""

from __future__ import annotations

import os
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from PIL import Image

from designer.models import (
    ManufacturingPlan,
    ManufacturingStep,
    QualityChecklistItem,
    StepDependency,
    StepMaterial,
)
from designer.services.warehouse_sync import sync_warehouse_steps_from_bom
from home.models import (
    ChatMessage,
    Client,
    Order,
    OrderImage,
    OrderModificationRequest,
    UserProfile,
)
from warehouse.models import ItemReservation, StorageSpace, StoredItem

DEFAULT_SEED_PASSWORD = "StremetTrain2026!"

DEMO_USERS: list[dict] = [
    {
        "username": "virtanen.mikko",
        "role": "admin",
        "email": "mikko.virtanen@stremet.fi",
        "first_name": "Mikko",
        "last_name": "Virtanen",
    },
    {
        "username": "nieminen.laura",
        "role": "designer",
        "email": "laura.nieminen@stremet.fi",
        "first_name": "Laura",
        "last_name": "Nieminen",
    },
    {
        "username": "koskinen.jukka",
        "role": "manufacturer",
        "email": "jukka.koskinen@stremet.fi",
        "first_name": "Jukka",
        "last_name": "Koskinen",
    },
    {
        "username": "lehtonen.sanna",
        "role": "warehouse",
        "email": "sanna.lehtonen@stremet.fi",
        "first_name": "Sanna",
        "last_name": "Lehtonen",
    },
    {
        "username": "makinen.eero",
        "role": "customer",
        "email": "eero.makinen@pohjanlift.fi",
        "first_name": "Eero",
        "last_name": "Mäkinen",
    },
    {
        "username": "rantanen.helena",
        "role": "customer",
        "email": "helena.rantanen@salohvac.fi",
        "first_name": "Helena",
        "last_name": "Rantanen",
    },
    {
        "username": "lindstrom.noora",
        "role": "customer",
        "email": "noora.lindstrom@medpanel.fi",
        "first_name": "Noora",
        "last_name": "Lindström",
    },
]

DEMO_CLIENTS: list[dict] = [
    {
        "email": "eero.makinen@pohjanlift.fi",
        "company_name": "Pohjan Lift Components Oy",
        "name": "Eero Mäkinen",
    },
    {
        "email": "helena.rantanen@salohvac.fi",
        "company_name": "Salo HVAC Engineering Oy",
        "name": "Helena Rantanen",
    },
    {
        "email": "antti.korhonen@koneturva.fi",
        "company_name": "Koneturva Guard Systems Oy",
        "name": "Antti Korhonen",
    },
    {
        "email": "liisa.hamalainen@latauskaari.fi",
        "company_name": "Latauskaari EV Structures Oy",
        "name": "Liisa Hämäläinen",
    },
    {
        "email": "noora.lindstrom@medpanel.fi",
        "company_name": "MedPanel Device Housings Oy",
        "name": "Noora Lindström",
    },
    {
        "email": "markus.salo@tuuli-inverter.fi",
        "company_name": "Tuuli-Inverter Cabinets Oy",
        "name": "Markus Salo",
    },
    {
        "email": "kaisa.toivonen@julkisivukiinnike.fi",
        "company_name": "Julkisivukiinnike Oy",
        "name": "Kaisa Toivonen",
    },
    {
        "email": "petri.heikkinen@logistiikkakori.fi",
        "company_name": "Logistiikkakori Assembly Oy",
        "name": "Petri Heikkinen",
    },
]


def _password() -> str:
    return os.environ.get("STREMET_SEED_PASSWORD", DEFAULT_SEED_PASSWORD)


def _tiny_png(filename: str) -> ContentFile:
    buf = BytesIO()
    Image.new("RGB", (160, 100), (210, 214, 218)).save(buf, format="PNG")
    return ContentFile(buf.getvalue(), name=filename)


def _ensure_storage_spaces() -> None:
    """Recreate slots 1..100 after ``flush`` (migration seed data is cleared too)."""
    if StorageSpace.objects.exists():
        return
    StorageSpace.objects.bulk_create(
        [StorageSpace(slot_number=i) for i in range(1, 101)]
    )


def _ensure_users() -> dict[str, User]:
    pw = _password()
    by_username: dict[str, User] = {}
    for spec in DEMO_USERS:
        user, _ = User.objects.get_or_create(
            username=spec["username"],
            defaults={
                "email": spec["email"],
                "first_name": spec["first_name"],
                "last_name": spec["last_name"],
            },
        )
        user.set_password(pw)
        user.email = spec["email"]
        user.first_name = spec["first_name"]
        user.last_name = spec["last_name"]
        user.save()
        profile, _ = UserProfile.objects.get_or_create(
            user=user, defaults={"role": spec["role"]}
        )
        if profile.role != spec["role"]:
            profile.role = spec["role"]
            profile.save(update_fields=["role"])
        by_username[spec["username"]] = user
    return by_username


def _ensure_material_catalog(designer: User) -> dict[str, ItemReservation]:
    specs = [
        (
            "SHE-DC01-2.0-ZE",
            "Sheet DC01+ZE 2.0 mm",
            "Cold-rolled mild steel, zinc coated; laser and brake.",
        ),
        (
            "SHE-304-1.5-2B",
            "Sheet AISI 304 1.5 mm",
            "Stainless for medical / food-adjacent enclosures.",
        ),
        (
            "TUB-S235-30X30X2",
            "Square tube 30x30x2 S235",
            "Frames and reinforcement.",
        ),
        (
            "HW-M6-A2-ASM01",
            "Hardware kit M6 A2",
            "Bolts, washers, nuts for assembly steps.",
        ),
        (
            "POW-RAL7035-EP",
            "Powder RAL 7035 light grey",
            "Standard enclosure finish.",
        ),
        (
            "SHE-S355MC-3.0",
            "Sheet S355MC 3.0 mm",
            "Structural brackets and load-bearing parts.",
        ),
    ]
    out: dict[str, ItemReservation] = {}
    for sku, name, desc in specs:
        ir, _ = ItemReservation.objects.update_or_create(
            sku=sku,
            defaults={
                "name": name,
                "description": desc,
                "created_by": designer,
            },
        )
        out[sku] = ir
    return out


def _seed_stock(materials: dict[str, ItemReservation], warehouse_user: User) -> None:
    used = set(StoredItem.objects.values_list("storage_space_id", flat=True))
    free = list(
        StorageSpace.objects.exclude(pk__in=used).order_by("slot_number")[:80]
    )
    idx = 0
    year = date.today().year
    counts = {
        "SHE-DC01-2.0-ZE": 24,
        "SHE-304-1.5-2B": 18,
        "TUB-S235-30X30X2": 40,
        "HW-M6-A2-ASM01": 60,
        "POW-RAL7035-EP": 30,
        "SHE-S355MC-3.0": 20,
    }
    for sku, n in counts.items():
        ir = materials[sku]
        for _ in range(n):
            if idx >= len(free):
                return
            StoredItem.objects.create(
                item_reservation=ir,
                storage_space=free[idx],
                label=f"LOT-{year}-{idx + 1:04d}",
                stored_by=warehouse_user,
            )
            idx += 1


def _build_orders() -> list[dict]:
    clients = [c["email"] for c in DEMO_CLIENTS]
    order_statuses = [
        "finishing",
        "shipping",
        "rolling",
        "finishing",
        "delivered",
        "raw_materials",
        "casting",
        "finishing",
        "shipping",
        "rolling",
        "delivered",
        "finishing",
        "melting",
        "finishing",
        "shipping",
        "delivered",
        "rolling",
        "finishing",
    ]
    plan_statuses = [
        "approved",
        "approved",
        "ready",
        "approved",
        "approved",
        "draft",
        "ready",
        "approved",
        "ready",
        "approved",
        "approved",
        "draft",
        "ready",
        "approved",
        "ready",
        "approved",
        "ready",
        "approved",
    ]
    rows = []
    for i in range(18):
        cid = clients[i % len(clients)]
        qty = (Decimal("0.04") + Decimal(i % 7) * Decimal("0.11")).quantize(
            Decimal("0.01")
        )
        steel = [
            "DC01+ZE",
            "S355MC",
            "AISI 304 (EN 1.4301)",
            "DX51D+Z275",
            "HC380LA",
            "AISI 316L",
        ][i % 6]
        form = [
            "Laser-cut flat blanks",
            "Folded seam assembly",
            "Welded frame",
            "Enclosure kit",
            "Bracket set",
        ][i % 5]
        dims = [
            "2.0mm x 1250mm x 2500mm",
            "1.5mm x 1000mm x 2000mm",
            "3.0mm x 1500mm x 3000mm",
            "1.2mm x 800mm x 1200mm",
            "2.5mm x 1250mm x 2500mm",
        ][i % 5]
        heat = i % 5 == 1
        ut = i % 6 == 2
        mill = i % 4 == 0
        notes = [
            "Powder RAL 7035 after weld; customer PPAP samples on slot 2.",
            "Tight flatness for elevator door stack; deburr all laser edges.",
            "MIG per WPS-STM-114; spot-check VT each 10th unit.",
            "Medical enclosure: no copper tooling contact; clean room hand-off.",
            "Deliver to Salo DC; use returnable stillages.",
        ][i % 5]
        rows.append(
            {
                "order_id": f"SO-2026-{9001 + i}",
                "client_email": cid,
                "steel_grade": steel,
                "product_form": form,
                "dimensions": dims,
                "quantity_tons": qty,
                "surface_finish": [
                    "Powder RAL 7035",
                    "Wet paint RAL 9006",
                    "Passivated",
                    "Glass bead + clear",
                ][i % 4],
                "heat_treatment": heat,
                "ultrasonic_test": ut,
                "mill_certificate": mill,
                "admin_notes": notes,
                "status": order_statuses[i],
                "plan_status": plan_statuses[i],
                "with_image": i % 2 == 0,
                "with_chat": i % 3 != 1,
                "with_mod": i in (2, 5, 11),
            }
        )
    return rows


def _create_manufacturing_graph(
    plan: ManufacturingPlan,
    plan_status: str,
    materials: dict[str, ItemReservation],
    order_index: int,
) -> None:
    if plan_status == "draft":
        ManufacturingStep.objects.create(
            plan=plan,
            name="Draft: nest and material review",
            description="Preliminary nesting; confirm sheet size and grain direction.",
            sequence_order=1,
            position_x=100.0,
            position_y=120.0,
            status="pending",
            step_kind=ManufacturingStep.STEP_KIND_MANUFACTURING,
            estimated_duration_hours=Decimal("2.0"),
        )
        return

    steel_sku = [
        "SHE-DC01-2.0-ZE",
        "SHE-S355MC-3.0",
        "SHE-304-1.5-2B",
    ][order_index % 3]
    steps_spec = [
        (
            "Laser cutting — nest L-{:03d}".format(order_index + 1),
            "Cut blanks per DXF rev C; micro-joints for small parts.",
            Decimal("3.5"),
            steel_sku,
            Decimal("2"),
            "sheet",
        ),
        (
            "Press brake — primary folds",
            "Set 88° tooling; check springback on first article.",
            Decimal("4.0"),
            None,
            None,
            None,
        ),
        (
            "MIG welding — frame",
            "WPS-STM-114, 0.8 mm wire; grind splatter before paint.",
            Decimal("6.0"),
            "TUB-S235-30X30X2",
            Decimal("4"),
            "pcs",
        ),
        (
            "Powder coating — RAL 7035",
            "Pre-treat iron phosphate; cure 180°C / 20 min.",
            Decimal("5.0"),
            "POW-RAL7035-EP",
            Decimal("1"),
            "kg",
        ),
        (
            "Final assembly + hardware",
            "Torque M6 to 10 Nm; apply QR traceability label.",
            Decimal("3.0"),
            "HW-M6-A2-ASM01",
            Decimal("2"),
            "kit",
        ),
    ]

    m_steps: list[ManufacturingStep] = []
    for seq, (name, desc, hrs, mat_sku, mat_qty, mat_unit) in enumerate(
        steps_spec, start=1
    ):
        st = ManufacturingStep.objects.create(
            plan=plan,
            name=name,
            description=desc,
            sequence_order=seq,
            position_x=80.0 + seq * 90,
            position_y=100.0 + (seq % 2) * 40,
            status="pending",
            step_kind=ManufacturingStep.STEP_KIND_MANUFACTURING,
            estimated_duration_hours=hrs,
            sop_text="Follow shop traveller STM-TR-{:04d}.".format(order_index + 1),
        )
        m_steps.append(st)
        if mat_sku:
            StepMaterial.objects.create(
                step=st,
                item_reservation=materials[mat_sku],
                specification=desc[:200],
                quantity=mat_qty,
                unit=mat_unit or "",
                storage_location=f"Warehouse A, rack B{seq}",
                storage_conditions="Dry, indoor",
            )
        qc_items = [
            ("First article dims vs drawing", "Within ±0.5 mm on critical edges"),
            ("Visual — burrs and scratches", "No sharp burrs; Ra acceptable for paint"),
            ("WPS parameters recorded", "Voltage/wire speed within WPS band"),
        ]
        if seq <= 2:
            qc_items = qc_items[:2]
        for qi, (qdesc, expected) in enumerate(qc_items):
            QualityChecklistItem.objects.create(
                step=st,
                description=qdesc,
                expected_result=expected,
                result_status=["pass", "pass", "pending", "na"][qi % 4],
            )

    for a, b in zip(m_steps, m_steps[1:]):
        StepDependency.objects.create(from_step=a, to_step=b)

    if plan_status in ("ready", "approved"):
        if order_index % 2 == 0:
            s0 = m_steps[0]
            s0.status = "completed"
            s0.started_at = timezone.now() - timedelta(days=3)
            s0.completed_at = timezone.now() - timedelta(days=2, hours=6)
            s0.execution_notes = "FA approved; production run cleared."
            s0.save()
        if order_index % 3 == 0 and len(m_steps) > 1:
            s1 = m_steps[1]
            s1.status = "in_progress"
            s1.started_at = timezone.now() - timedelta(hours=4)
            s1.save()

    sync_warehouse_steps_from_bom(plan)

    if plan_status in ("ready", "approved") and order_index % 2 == 0 and m_steps:
        pickup = ManufacturingStep.objects.filter(
            plan=plan,
            step_kind=ManufacturingStep.STEP_KIND_WAREHOUSE_PICKUP,
            picks_for=m_steps[0],
        ).first()
        if pickup:
            pickup.status = "completed"
            pickup.completed_at = timezone.now() - timedelta(days=2, hours=8)
            pickup.save()


class Command(BaseCommand):
    help = (
        "DESTRUCTIVE: flush entire database, then load Stremet sample sheet-metal data."
    )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.WARNING(
                "Flushing all database tables (same as manage.py flush --no-input)..."
            )
        )
        call_command("flush", interactive=False, verbosity=0)
        self.stdout.write("Running migrate (content types, permissions)...")
        call_command("migrate", interactive=False, verbosity=0)
        _ensure_storage_spaces()

        order_specs = _build_orders()
        with transaction.atomic():
            self.stdout.write("Seeding users, clients, orders, plans, warehouse...")
            users = _ensure_users()
            designer = users["nieminen.laura"]
            wh_user = users["lehtonen.sanna"]

            self.stdout.write("Material catalog + warehouse stock...")
            materials = _ensure_material_catalog(designer)
            _seed_stock(materials, wh_user)

            self.stdout.write("Clients and orders...")
            client_by_email = {}
            for c in DEMO_CLIENTS:
                client_by_email[c["email"]] = Client.objects.create(
                    email=c["email"],
                    company_name=c["company_name"],
                    name=c["name"],
                )

            admin_u = users["virtanen.mikko"]
            cust_elev = users["makinen.eero"]

            for idx, spec in enumerate(order_specs):
                cl = client_by_email[spec["client_email"]]
                td = date.today() + timedelta(days=14 + (idx % 10) * 3)
                order = Order.objects.create(
                    order_id=spec["order_id"],
                    client=cl,
                    steel_grade=spec["steel_grade"],
                    product_form=spec["product_form"],
                    dimensions=spec["dimensions"],
                    quantity_tons=spec["quantity_tons"],
                    surface_finish=spec["surface_finish"],
                    heat_treatment=spec["heat_treatment"],
                    ultrasonic_test=spec["ultrasonic_test"],
                    mill_certificate=spec["mill_certificate"],
                    admin_notes=spec["admin_notes"],
                    status=spec["status"],
                    target_delivery=td,
                )
                if spec["with_image"]:
                    OrderImage.objects.create(
                        order=order,
                        image=_tiny_png(f"ref_{order.order_id}.png"),
                    )
                if spec["with_mod"]:
                    OrderModificationRequest.objects.create(
                        order=order,
                        request_text="Please confirm hole pattern matches mounting plate rev D — customer sent updated STEP yesterday.",
                        is_approved=True if idx % 2 == 0 else None,
                    )
                if spec["with_chat"]:
                    ChatMessage.objects.create(
                        order=order,
                        sender=cust_elev if idx % 2 == 0 else admin_u,
                        message="Can we pull in delivery by two days for line fit-up at our Salo site?",
                        step_context="Finishing & Inspection",
                    )
                    ChatMessage.objects.create(
                        order=order,
                        sender=admin_u if idx % 2 == 0 else designer,
                        message="We can ship calendar week 12 if powder batch clears QC Friday. I'll update the traveller.",
                        step_context="Ready for Shipping",
                    )
                    if idx % 4 == 0:
                        ChatMessage.objects.create(
                            order=order,
                            sender=None,
                            message="Site logistics: please confirm stillage return process for this delivery.",
                            step_context="Order Received",
                        )

                plan = ManufacturingPlan.objects.create(
                    order=order,
                    name=f"Manufacturing plan — {order.order_id}",
                    description=(
                        "Standard routing: laser cutting, press brake, welding, "
                        "powder coating, final assembly."
                    ),
                    designer=designer,
                    status=spec["plan_status"],
                )
                _create_manufacturing_graph(
                    plan, spec["plan_status"], materials, idx
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Stremet sample data ready: {len(order_specs)} orders, "
                f"{len(DEMO_USERS)} users. Password: STREMET_SEED_PASSWORD "
                f"(see STREMET_DEMO_DATA.md)."
            )
        )
