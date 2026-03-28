"""
Auto-create/remove warehouse pickup steps from manufacturing-step BOM lines.
Pickup steps have no BOM; materials are read from picks_for manufacturing step.
"""

from __future__ import annotations

from django.db import transaction
from django.db.models import Max

from designer.models import ManufacturingStep, StepDependency


def _m_needs_pickup(m_step: ManufacturingStep) -> bool:
    if m_step.step_kind != ManufacturingStep.STEP_KIND_MANUFACTURING:
        return False
    return m_step.materials.exists()


def _pred_ids_for_target(target: ManufacturingStep) -> list[int]:
    return list(
        StepDependency.objects.filter(to_step=target).values_list(
            "from_step_id", flat=True
        )
    )


def _remove_pickup_step(m_step: ManufacturingStep, pickup: ManufacturingStep) -> None:
    preds = _pred_ids_for_target(pickup)
    StepDependency.objects.filter(to_step=pickup).delete()
    StepDependency.objects.filter(from_step=pickup).delete()
    pickup.delete()
    for pid in preds:
        if pid == m_step.pk:
            continue
        StepDependency.objects.get_or_create(from_step_id=pid, to_step=m_step)


def _rewire_pickup_edges(m_step: ManufacturingStep, pickup: ManufacturingStep) -> None:
    """
    Desired: preds -> pickup -> m_step.
    Predecessors are incoming to pickup if any; else incoming to M (excluding pickup).
    """
    preds = _pred_ids_for_target(pickup)
    if not preds:
        preds = [
            pid
            for pid in _pred_ids_for_target(m_step)
            if pid != pickup.pk
        ]

    StepDependency.objects.filter(to_step=m_step).exclude(from_step=pickup).delete()
    StepDependency.objects.filter(to_step=pickup).delete()

    for pid in preds:
        StepDependency.objects.get_or_create(from_step_id=pid, to_step=pickup)
    StepDependency.objects.get_or_create(from_step=pickup, to_step=m_step)


def _create_pickup_step(plan, m_step: ManufacturingStep) -> ManufacturingStep:
    max_seq = ManufacturingStep.objects.filter(plan=plan).aggregate(m=Max("sequence_order"))[
        "m"
    ] or 0
    return ManufacturingStep.objects.create(
        plan=plan,
        name=f"Pick materials for: {m_step.name}",
        step_kind=ManufacturingStep.STEP_KIND_WAREHOUSE_PICKUP,
        picks_for=m_step,
        sequence_order=max_seq + 1,
        position_x=m_step.position_x + 40,
        position_y=m_step.position_y - 80,
    )


@transaction.atomic
def sync_warehouse_steps_from_bom(plan) -> None:
    """Ensure each manufacturing step with BOM lines has a pickup step wired in the DAG."""
    m_steps = plan.steps.filter(
        step_kind=ManufacturingStep.STEP_KIND_MANUFACTURING
    ).prefetch_related("materials")

    for m in m_steps:
        pickup = ManufacturingStep.objects.filter(
            plan=plan,
            step_kind=ManufacturingStep.STEP_KIND_WAREHOUSE_PICKUP,
            picks_for=m,
        ).first()

        if not _m_needs_pickup(m):
            if pickup:
                _remove_pickup_step(m, pickup)
            continue

        if pickup is None:
            pickup = _create_pickup_step(plan, m)

        _rewire_pickup_edges(m, pickup)
