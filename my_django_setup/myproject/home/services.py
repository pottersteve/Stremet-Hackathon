from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Prefetch
from django.utils.dateformat import format

from designer.models import ManufacturingPlan, ManufacturingStep
from designer.services.plans import get_or_create_plan_for_order

from .models import ChatMessage, Client, Order, OrderImage


def create_order_from_post(request):
    """
    Create Order, ManufacturingPlan, and optional images from POST.
    Returns (order, None) on success or (None, error_message) on failure.
    """
    company_name = request.POST.get("company_name")
    client_email = (request.POST.get("client_email") or "").strip() or (
        request.user.email or ""
    )
    if not client_email:
        return None, "Contact email is required."

    try:
        client, created = Client.objects.get_or_create(
            email=client_email,
            defaults={"company_name": company_name},
        )
        if not created and company_name and client.company_name != company_name:
            client.company_name = company_name
            client.save(update_fields=["company_name"])

        thickness = request.POST.get("dim_thickness") or "0"
        width = request.POST.get("dim_width") or "0"
        length = request.POST.get("dim_length") or "0"
        dimensions_str = f"{thickness}mm x {width}mm x {length}mm"

        qty_raw = request.POST.get("quantity_tons")
        if not qty_raw:
            qty = Decimal("0")
        else:
            try:
                qty = Decimal(str(qty_raw))
            except (InvalidOperation, ValueError, TypeError):
                return None, "Invalid quantity."

        new_order = Order.objects.create(
            order_id=request.POST.get("order_id"),
            client=client,
            target_delivery=request.POST.get("target_delivery"),
            steel_grade=request.POST.get("steel_grade"),
            product_form=request.POST.get("product_form"),
            dimensions=dimensions_str,
            quantity_tons=qty,
            surface_finish=request.POST.get("surface_finish"),
            heat_treatment=(request.POST.get("heat_treatment") == "yes"),
            ultrasonic_test=(request.POST.get("ultrasonic_test") == "yes"),
            mill_certificate=(request.POST.get("mill_certificate") == "yes"),
            blueprint_file=request.FILES.get("blueprint_file"),
            admin_notes=request.POST.get("admin_notes"),
        )

        images = request.FILES.getlist("reference_images")
        for img in images:
            if img:
                OrderImage.objects.create(order=new_order, image=img)

        get_or_create_plan_for_order(new_order)

        return new_order, None
    except (ValidationError, IntegrityError, ValueError, TypeError) as e:
        return None, f"Error saving order: {e}"


def lookup_order_with_chats(order_id):
    """Return (order, chat_messages) or (None, []) if not found."""
    if not order_id:
        return None, []
    try:
        order = Order.objects.get(order_id=order_id)
        chat_msgs = order.chat_logs.all().order_by("timestamp")
        return order, list(chat_msgs)
    except Order.DoesNotExist:
        return None, []


def _order_fallback_stage_percent(order):
    stages = [c[0] for c in Order.STAGE_CHOICES]
    try:
        idx = stages.index(order.status)
        return int(100 * (idx + 1) / len(stages))
    except ValueError:
        return 0


def _vis_node_color(status):
    if status in ("completed", "skipped"):
        return {
            "background": "#198754",
            "border": "#146c43",
            "highlight": {"background": "#20c997", "border": "#198754"},
        }
    if status == "in_progress":
        return {
            "background": "#fd7e14",
            "border": "#ca6510",
            "highlight": {"background": "#ffc107", "border": "#fd7e14"},
        }
    return {
        "background": "#6c757d",
        "border": "#565e64",
        "highlight": {"background": "#adb5bd", "border": "#6c757d"},
    }


def customer_order_progress_context(order):
    """
    Manufacturing steps only (no warehouse_pickup). For customer vis-network + progress bar.
    """
    fallback = _order_fallback_stage_percent(order)
    plan = (
        ManufacturingPlan.objects.filter(order_id=order.pk)
        .prefetch_related(
            Prefetch(
                "steps",
                queryset=ManufacturingStep.objects.order_by(
                    "sequence_order", "pk"
                ).prefetch_related("outgoing_dependencies__to_step"),
            )
        )
        .first()
    )

    if not plan:
        empty_graph = {"nodes": [], "edges": []}
        return {
            "has_plan": False,
            "has_mfg_steps": False,
            "nodes": [],
            "edges": [],
            "done_count": 0,
            "total_count": 0,
            "step_percent": None,
            "fallback_stage_percent": fallback,
            "graph": empty_graph,
        }

    mfg_steps = [
        s
        for s in plan.steps.all()
        if s.step_kind == ManufacturingStep.STEP_KIND_MANUFACTURING
    ]
    mfg_ids = {s.pk for s in mfg_steps}

    nodes = []
    for s in mfg_steps:
        nodes.append(
            {
                "id": str(s.pk),
                "label": s.name,
                "x": float(s.position_x),
                "y": float(s.position_y),
                "color": _vis_node_color(s.status),
                "font": {"color": "#ffffff"},
                "title": f"{s.name}\nStatus: {s.get_status_display()}",
            }
        )

    edges = []
    seen = set()
    for s in mfg_steps:
        for dep in s.outgoing_dependencies.all():
            tid = dep.to_step_id
            if tid in mfg_ids:
                key = (s.pk, tid)
                if key not in seen:
                    seen.add(key)
                    edges.append({"from": str(s.pk), "to": str(tid)})

    done_count = sum(
        1 for s in mfg_steps if s.status in ("completed", "skipped")
    )
    total_count = len(mfg_steps)
    step_percent = (
        int(100 * done_count / total_count) if total_count else None
    )
    graph = {"nodes": nodes, "edges": edges}

    return {
        "has_plan": True,
        "has_mfg_steps": total_count > 0,
        "nodes": nodes,
        "edges": edges,
        "done_count": done_count,
        "total_count": total_count,
        "step_percent": step_percent,
        "fallback_stage_percent": fallback,
        "graph": graph,
    }


def manufacturing_steps_summary_lines(order):
    """Human-readable manufacturing step lines for AI context (no warehouse steps)."""
    plan = (
        ManufacturingPlan.objects.filter(order_id=order.pk)
        .prefetch_related("steps")
        .first()
    )
    if not plan:
        return ["Manufacturing plan: (none yet)."]
    mfg = [
        s
        for s in plan.steps.all()
        if s.step_kind == ManufacturingStep.STEP_KIND_MANUFACTURING
    ]
    if not mfg:
        return ["Manufacturing plan: no manufacturing steps defined yet."]
    lines = ["Production steps (manufacturing):"]
    for s in sorted(mfg, key=lambda x: (x.sequence_order, x.pk)):
        lines.append(f"  - {s.name}: {s.get_status_display()}")
    return lines


def create_chat_message_from_request(request):
    """
    Persist a chat message from POST (multipart or form).
    Returns (payload_dict, None) or (None, error_string).
    """
    order_id = request.POST.get("order_id")
    message_text = request.POST.get("chat_message")
    step_context = request.POST.get("step_context")
    attachment = request.FILES.get("chat_attachment")

    order = Order.objects.filter(order_id=order_id).first()
    if not order:
        return None, "Order not found."

    actual_user = request.user if request.user.is_authenticated else None
    new_msg = ChatMessage.objects.create(
        order=order,
        sender=actual_user,
        message=message_text,
        step_context=step_context,
        attachment=attachment,
    )

    return {
        "success": True,
        "message": new_msg.message,
        "step_context": new_msg.step_context,
        "attachment_url": new_msg.attachment.url if new_msg.attachment else None,
        "timestamp": format(new_msg.timestamp, "M d, Y - g:i A"),
    }, None
