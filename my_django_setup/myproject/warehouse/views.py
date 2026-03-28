from django.contrib import messages
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from designer.models import ManufacturingStep
from home.permissions import warehouse_required

from .forms import StoredItemReceiveForm, WarehouseItemReservationForm
from .models import ItemReservation, StoredItem
from .services import (
    can_fulfill_pickup,
    consume_stock_for_pickup,
    plan_work_summary_pickup,
    suggest_free_slot,
    warehouse_orders_queryset,
    pickup_requirements,
)


def _pickup_step_in_queue_or_404(plan_id, step_id):
    step = get_object_or_404(ManufacturingStep, pk=step_id, plan_id=plan_id)
    plan = step.plan
    if plan.status not in ("ready", "approved") or plan.order.status == "delivered":
        raise Http404()
    if step.step_kind != ManufacturingStep.STEP_KIND_WAREHOUSE_PICKUP:
        raise Http404()
    return step


@warehouse_required
def warehouse_dashboard(request):
    return render(request, "warehouse/hub.html", {})


@warehouse_required
def warehouse_store(request):
    suggested_slot = suggest_free_slot()
    return render(
        request,
        "warehouse/store.html",
        {
            "suggested_slot": suggested_slot,
            "receive_form": StoredItemReceiveForm(),
        },
    )


@warehouse_required
def warehouse_pickup_queue(request):
    search = request.GET.get("q", "").strip()
    orders = warehouse_orders_queryset()
    if search:
        orders = orders.filter(
            Q(order_id__icontains=search) | Q(client__company_name__icontains=search)
        ).distinct()

    rows = []
    for order in orders:
        summary = plan_work_summary_pickup(order.manufacturing_plan)
        rows.append({"order": order, **summary})

    return render(
        request,
        "warehouse/pickup_queue.html",
        {"rows": rows, "search_query": search},
    )


@warehouse_required
def warehouse_receive(request):
    if request.method != "POST":
        return redirect("warehouse_store")

    form = StoredItemReceiveForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Invalid form.")
        return redirect("warehouse_store")

    slot = suggest_free_slot()
    if slot is None:
        messages.error(request, "No free storage slots (warehouse full).")
        return redirect("warehouse_store")

    StoredItem.objects.create(
        item_reservation=form.cleaned_data["item_reservation"],
        storage_space=slot,
        label=form.cleaned_data.get("label") or "",
        stored_by=request.user,
    )
    messages.success(
        request,
        f"Stored in slot {slot.slot_number}.",
    )
    return redirect("warehouse_store")


@warehouse_required
def warehouse_pickup_detail(request, plan_id, step_id):
    step = _pickup_step_in_queue_or_404(plan_id, step_id)
    plan = step.plan
    order = plan.order
    m_step = step.picks_for
    if m_step is None:
        raise Http404()

    reqs = pickup_requirements(m_step)
    ok = can_fulfill_pickup(m_step)

    if request.method == "POST" and request.POST.get("confirm_pickup"):
        if not ok:
            messages.error(
                request,
                "Not enough stock in warehouse to fulfill this pickup.",
            )
        else:
            try:
                consume_stock_for_pickup(m_step)
            except ValueError as e:
                messages.error(request, str(e))
            else:
                step.status = "completed"
                step.completed_at = timezone.now()
                if step.started_at is None:
                    step.started_at = timezone.now()
                step.save(
                    update_fields=["status", "completed_at", "started_at"]
                )
                messages.success(request, "Pickup completed; manufacturing can proceed.")
                return redirect("warehouse_pickup_queue")

    return render(
        request,
        "warehouse/pickup_detail.html",
        {
            "order": order,
            "plan": plan,
            "step": step,
            "m_step": m_step,
            "requirements": reqs,
            "can_fulfill": ok,
        },
    )


@warehouse_required
def warehouse_reservation_create(request):
    if request.method == "POST":
        form = WarehouseItemReservationForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.created_by = request.user
            obj.save()
            messages.success(request, "Item reservation created.")
            return redirect("warehouse_store")
    else:
        form = WarehouseItemReservationForm()
    return render(
        request,
        "warehouse/reservation_form.html",
        {"form": form},
    )


@warehouse_required
def warehouse_inventory(request):
    items = StoredItem.objects.select_related(
        "item_reservation", "storage_space"
    ).order_by("storage_space__slot_number")
    return render(
        request,
        "warehouse/inventory.html",
        {"items": items},
    )
