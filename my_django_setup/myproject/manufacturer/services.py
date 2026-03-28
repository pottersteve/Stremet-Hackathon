"""DAG-ready steps and manufacturer work queue (uses designer models)."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from django.db.models import QuerySet

if TYPE_CHECKING:
    from designer.models import ManufacturingPlan, ManufacturingStep
    from home.models import Order

MANUFACTURER_PLAN_STATUSES = ("ready", "approved")


def manufacturer_orders_queryset() -> QuerySet[Order]:
    from home.models import Order

    return (
        Order.objects.filter(manufacturing_plan__status__in=MANUFACTURER_PLAN_STATUSES)
        .exclude(status="delivered")
        .select_related("client", "manufacturing_plan")
        .order_by("-created_at")
    )


def step_dependencies_satisfied(step: ManufacturingStep) -> bool:
    for dep in step.incoming_dependencies.select_related("from_step").all():
        if dep.from_step.status not in ("completed", "skipped"):
            return False
    return True


def step_is_actionable(step: ManufacturingStep) -> bool:
    if step.status in ("completed", "skipped"):
        return False
    return step_dependencies_satisfied(step)


def ready_steps_for_plan(plan: ManufacturingPlan) -> list[ManufacturingStep]:
    steps = list(plan.steps.prefetch_related("incoming_dependencies__from_step").all())
    return [s for s in steps if step_is_actionable(s)]


def primary_ready_step(
    ready_steps: list[ManufacturingStep],
) -> ManufacturingStep | None:
    if not ready_steps:
        return None
    in_prog = [s for s in ready_steps if s.status == "in_progress"]
    if in_prog:
        return min(in_prog, key=lambda x: (x.sequence_order, x.pk))
    pending = [s for s in ready_steps if s.status == "pending"]
    if pending:
        return min(pending, key=lambda x: (x.sequence_order, x.pk))
    return min(ready_steps, key=lambda x: (x.sequence_order, x.pk))


class PlanWorkSummary(TypedDict):
    plan: ManufacturingPlan
    ready_steps: list[ManufacturingStep]
    primary_step: ManufacturingStep | None
    other_ready_steps: list[ManufacturingStep]


def plan_work_summary(plan: ManufacturingPlan) -> PlanWorkSummary:
    ready = ready_steps_for_plan(plan)
    primary = primary_ready_step(ready)
    primary_id = primary.pk if primary else None
    other_ready = [s for s in ready if s.pk != primary_id]
    return {
        "plan": plan,
        "ready_steps": ready,
        "primary_step": primary,
        "other_ready_steps": other_ready,
    }
