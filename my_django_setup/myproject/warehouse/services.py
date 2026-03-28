"""Slot suggestion, stock counts, and pickup consumption."""

from __future__ import annotations

import math

from django.db import transaction
from django.db.models import Count

from designer.models import ManufacturingStep
from warehouse.models import StorageSpace, StoredItem

MANUFACTURER_PLAN_STATUSES = ("ready", "approved")


def suggest_free_slot() -> StorageSpace | None:
    used = StoredItem.objects.values_list("storage_space_id", flat=True)
    return (
        StorageSpace.objects.exclude(pk__in=used).order_by("slot_number").first()
    )


def stock_counts_by_reservation() -> dict[int, int]:
    qs = (
        StoredItem.objects.values("item_reservation_id")
        .annotate(c=Count("id"))
        .order_by()
    )
    return {row["item_reservation_id"]: row["c"] for row in qs}


def stock_count(reservation_id: int) -> int:
    return StoredItem.objects.filter(item_reservation_id=reservation_id).count()


def pickup_requirements(m_step: ManufacturingStep) -> list[dict]:
    """Per BOM line: reservation, qty required (as unit count), available in warehouse."""
    counts = stock_counts_by_reservation()
    out = []
    for line in m_step.materials.select_related("item_reservation").all():
        rid = line.item_reservation_id
        req = max(1, int(math.ceil(float(line.quantity or 1))))
        out.append(
            {
                "line": line,
                "reservation": line.item_reservation,
                "required": req,
                "available": counts.get(rid, 0),
            }
        )
    return out


def can_fulfill_pickup(m_step: ManufacturingStep) -> bool:
    for row in pickup_requirements(m_step):
        if row["available"] < row["required"]:
            return False
    return True


@transaction.atomic
def consume_stock_for_pickup(m_step: ManufacturingStep) -> None:
    """
    Remove StoredItems (lowest slot first) to satisfy each BOM line quantity.
    """
    for row in pickup_requirements(m_step):
        rid = row["reservation"].pk
        need = row["required"]
        items = list(
            StoredItem.objects.filter(item_reservation_id=rid)
            .select_related("storage_space")
            .order_by("storage_space__slot_number")[:need]
        )
        if len(items) < need:
            raise ValueError(
                f"Not enough stock for {row['reservation']}: need {need}, have {len(items)}"
            )
        for it in items:
            it.delete()


def warehouse_orders_queryset():
    from home.models import Order

    return (
        Order.objects.filter(manufacturing_plan__status__in=MANUFACTURER_PLAN_STATUSES)
        .exclude(status="delivered")
        .select_related("client", "manufacturing_plan")
        .order_by("-created_at")
    )


def plan_work_summary_pickup(plan):
    from manufacturer.services import primary_ready_step, ready_pickup_steps_for_plan

    ready = ready_pickup_steps_for_plan(plan)
    primary = primary_ready_step(ready)
    primary_id = primary.pk if primary else None
    return {
        "plan": plan,
        "ready_steps": ready,
        "primary_step": primary,
        "other_ready_steps": [s for s in ready if s.pk != primary_id],
    }
