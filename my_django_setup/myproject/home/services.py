import json
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils.dateformat import format

from designer.services.plans import get_or_create_plan_for_order

from .models import ChatMessage, Client, Order, OrderImage, OrderItem


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


def apply_flowchart_step_update(item_id, step_number, is_done):
    """
    Update a single flowchart step on an OrderItem.
    Returns None on success or an error string.
    """
    try:
        item = OrderItem.objects.get(id=item_id)
    except OrderItem.DoesNotExist:
        return "Item not found."

    if step_number == 1:
        item.step_1_programming = is_done
    elif step_number == 2:
        item.step_2_cutting = is_done
    elif step_number == 3:
        item.step_3_forming = is_done
    elif step_number == 4:
        item.step_4_joining = is_done
    elif step_number == 5:
        item.step_5_delivery = is_done
    else:
        return "Invalid step."

    item.save()
    return None


def parse_flowchart_status_post(body):
    """Parse JSON body for flowchart AJAX. Returns dict or raises ValueError/JSONDecodeError."""
    data = json.loads(body)
    item_id = data.get("item_id")
    step_number = data.get("step")
    is_done = data.get("is_done")
    if item_id is None or step_number is None or is_done is None:
        raise ValueError("Missing fields")
    return {"item_id": item_id, "step_number": step_number, "is_done": is_done}


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
