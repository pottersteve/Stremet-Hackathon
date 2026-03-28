from datetime import date

import pytest

from designer.models import ManufacturingPlan, ManufacturingStep
from designer.services.graph import save_graph_from_payload
from home.models import Client, Order


@pytest.mark.django_db
def test_save_graph_rejects_cycle():
    client = Client.objects.create(
        email="designer-graph@example.com", company_name="Co"
    )
    order = Order.objects.create(
        order_id="GRAPH-ORDER-1",
        client=client,
        target_delivery=date.today(),
        steel_grade="X",
        dimensions="1x1x1",
        quantity_tons=1,
    )
    plan = ManufacturingPlan.objects.create(order=order, name="Plan")
    step_a = ManufacturingStep.objects.create(plan=plan, name="A", sequence_order=1)
    step_b = ManufacturingStep.objects.create(plan=plan, name="B", sequence_order=2)

    payload = {
        "nodes": [
            {"id": step_a.pk, "x": 0, "y": 0},
            {"id": step_b.pk, "x": 1, "y": 1},
        ],
        "edges": [
            {"from": step_a.pk, "to": step_b.pk},
            {"from": step_b.pk, "to": step_a.pk},
        ],
    }
    err = save_graph_from_payload(plan, payload)
    assert err is not None
    assert "cycle" in err.lower()
