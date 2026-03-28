from designer.models import ManufacturingPlan
from home.models import Order


def get_or_create_plan_for_order(order, name=None):
    """Ensure a ManufacturingPlan exists for this order (OneToOne)."""
    plan, _created = ManufacturingPlan.objects.get_or_create(
        order=order,
        defaults={"name": name or f"Plan for {order.order_id}"},
    )
    return plan


def backfill_plans_for_received_orders():
    """Create plans for received orders that do not have one yet."""
    qs = Order.objects.filter(status="order_received", manufacturing_plan__isnull=True)
    for order in qs:
        get_or_create_plan_for_order(order)
