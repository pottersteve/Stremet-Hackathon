from datetime import date

import pytest

from designer.models import ManufacturingPlan, ManufacturingStep, StepDependency
from home.models import Client, Order
from home.services import customer_order_progress_context


@pytest.mark.django_db
def test_customer_progress_manufacturing_only_and_edges():
    client = Client.objects.create(email="c@example.com", company_name="Co")
    order = Order.objects.create(
        order_id="PROG-1",
        client=client,
        target_delivery=date.today(),
        steel_grade="S355",
        dimensions="1x1x1",
        quantity_tons=1,
    )
    plan = ManufacturingPlan.objects.create(order=order, name="Plan")
    m1 = ManufacturingStep.objects.create(
        plan=plan,
        name="Cut",
        step_kind=ManufacturingStep.STEP_KIND_MANUFACTURING,
        status="completed",
        position_x=0,
        position_y=0,
    )
    wh = ManufacturingStep.objects.create(
        plan=plan,
        name="Warehouse pick",
        step_kind=ManufacturingStep.STEP_KIND_WAREHOUSE_PICKUP,
        status="completed",
        position_x=100,
        position_y=0,
    )
    m2 = ManufacturingStep.objects.create(
        plan=plan,
        name="Weld",
        step_kind=ManufacturingStep.STEP_KIND_MANUFACTURING,
        status="pending",
        position_x=200,
        position_y=0,
    )
    StepDependency.objects.create(from_step=m1, to_step=wh)
    StepDependency.objects.create(from_step=wh, to_step=m2)
    StepDependency.objects.create(from_step=m1, to_step=m2)

    ctx = customer_order_progress_context(order)

    assert ctx["has_plan"] is True
    assert ctx["has_mfg_steps"] is True
    assert {n["label"] for n in ctx["nodes"]} == {"Cut", "Weld"}
    assert ctx["total_count"] == 2
    assert ctx["done_count"] == 1
    assert ctx["step_percent"] == 50
    assert len(ctx["edges"]) == 1
    assert ctx["edges"][0]["from"] == str(m1.pk)
    assert ctx["edges"][0]["to"] == str(m2.pk)


@pytest.mark.django_db
def test_customer_progress_no_plan_fallback_percent():
    client = Client.objects.create(email="d@example.com", company_name="Co2")
    order = Order.objects.create(
        order_id="PROG-2",
        client=client,
        target_delivery=date.today(),
        steel_grade="S355",
        dimensions="1x1x1",
        quantity_tons=1,
        status="order_received",
    )
    ctx = customer_order_progress_context(order)
    assert ctx["has_plan"] is False
    assert ctx["step_percent"] is None
    assert ctx["fallback_stage_percent"] > 0
    assert ctx["graph"]["nodes"] == []
