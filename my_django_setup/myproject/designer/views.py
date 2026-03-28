import json

from django.contrib import messages
from django.db import models as db_models
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from designer.services.graph import save_graph_from_payload
from designer.services.plans import backfill_plans_for_received_orders
from designer.services.warehouse_sync import sync_warehouse_steps_from_bom
from home.models import Order
from home.permissions import designer_required
from warehouse.models import ItemReservation

from .forms import (
    DesignerQualityChecklistFormSet,
    ItemReservationForm,
    ManufacturingPlanForm,
    ManufacturingStepCreateForm,
    ManufacturingStepForm,
    StepMaterialFormSet,
)
from .models import (
    ManufacturingPlan,
    ManufacturingStep,
    StepDependency,
)

# ------------------------------------------------------------------
# Dashboard — list open orders
# ------------------------------------------------------------------


@designer_required
def designer_dashboard(request):
    backfill_plans_for_received_orders()

    search_query = request.GET.get("q", "").strip()
    orders = Order.objects.filter(status="order_received").select_related(
        "client", "manufacturing_plan"
    )
    if search_query:
        orders = orders.filter(
            Q(order_id__icontains=search_query)
            | Q(client__company_name__icontains=search_query)
        )
    return render(
        request,
        "designer/dashboard.html",
        {
            "orders": orders,
            "search_query": search_query,
        },
    )


# ------------------------------------------------------------------
# Order detail — read-only view, option to create plan
# ------------------------------------------------------------------


@designer_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, pk=order_id, status="order_received")
    plan = order.manufacturing_plan
    return render(
        request,
        "designer/order_detail.html",
        {
            "order": order,
            "plan": plan,
        },
    )


# ------------------------------------------------------------------
# Plan editor — graph view + plan metadata
# ------------------------------------------------------------------


@designer_required
def plan_editor(request, plan_id):
    plan = get_object_or_404(ManufacturingPlan, pk=plan_id)
    sync_warehouse_steps_from_bom(plan)

    if request.method == "POST":
        form = ManufacturingPlanForm(request.POST, instance=plan)
        if form.is_valid():
            raw_graph = request.POST.get("graph_payload", "").strip()
            graph_data = None
            if raw_graph:
                try:
                    graph_data = json.loads(raw_graph)
                except json.JSONDecodeError:
                    messages.error(
                        request,
                        "Invalid graph data. Please reload the page and try again.",
                    )
                    step_form = ManufacturingStepCreateForm()
                    steps = plan.steps.all()
                    return render(
                        request,
                        "designer/plan_editor.html",
                        {
                            "plan": plan,
                            "form": form,
                            "step_form": step_form,
                            "steps": steps,
                        },
                    )

            try:
                with transaction.atomic():
                    form.save()
                    if graph_data is not None:
                        err = save_graph_from_payload(plan, graph_data)
                        if err:
                            raise ValueError(err)
            except ValueError as e:
                messages.error(request, str(e))
                step_form = ManufacturingStepCreateForm()
                steps = plan.steps.all()
                return render(
                    request,
                    "designer/plan_editor.html",
                    {
                        "plan": plan,
                        "form": form,
                        "step_form": step_form,
                        "steps": steps,
                    },
                )

            sync_warehouse_steps_from_bom(plan)
            if graph_data is not None:
                messages.success(request, "Plan and manufacturing graph saved.")
            else:
                messages.success(request, "Plan updated.")
            return redirect("designer_plan_editor", plan_id=plan.pk)
    else:
        form = ManufacturingPlanForm(instance=plan)

    step_form = ManufacturingStepCreateForm()
    steps = plan.steps.all()

    return render(
        request,
        "designer/plan_editor.html",
        {
            "plan": plan,
            "form": form,
            "step_form": step_form,
            "steps": steps,
        },
    )


# ------------------------------------------------------------------
# Add a step to a plan
# ------------------------------------------------------------------


@designer_required
def add_step(request, plan_id):
    plan = get_object_or_404(ManufacturingPlan, pk=plan_id)

    if request.method == "POST":
        form = ManufacturingStepCreateForm(request.POST, request.FILES)
        if form.is_valid():
            step = form.save(commit=False)
            step.plan = plan
            max_seq = plan.steps.aggregate(m=db_models.Max("sequence_order"))["m"] or 0
            step.sequence_order = max_seq + 1
            existing_count = plan.steps.count()
            step.position_x = 100 + (existing_count * 180)
            step.position_y = 200
            step.step_kind = ManufacturingStep.STEP_KIND_MANUFACTURING
            step.save()
            messages.success(request, f"Step '{step.name}' added.")
        else:
            messages.error(request, "Could not add step. Check the form.")

    return redirect("designer_plan_editor", plan_id=plan.pk)


# ------------------------------------------------------------------
# Step detail — edit step, quality checklist, materials
# ------------------------------------------------------------------


@designer_required
def step_detail(request, plan_id, step_id):
    plan = get_object_or_404(ManufacturingPlan, pk=plan_id)
    step = get_object_or_404(ManufacturingStep, pk=step_id, plan=plan)

    if step.step_kind == ManufacturingStep.STEP_KIND_WAREHOUSE_PICKUP:
        m_step = step.picks_for
        return render(
            request,
            "designer/warehouse_pickup_step.html",
            {
                "plan": plan,
                "step": step,
                "m_step": m_step,
            },
        )

    if request.method == "POST":
        form = ManufacturingStepForm(request.POST, request.FILES, instance=step)
        checklist_formset = DesignerQualityChecklistFormSet(
            request.POST, instance=step, prefix="quality"
        )
        material_formset = StepMaterialFormSet(
            request.POST, instance=step, prefix="material"
        )

        if (
            form.is_valid()
            and checklist_formset.is_valid()
            and material_formset.is_valid()
        ):
            form.save()
            checklist_formset.save()
            material_formset.save()
            sync_warehouse_steps_from_bom(plan)
            messages.success(request, f"Step '{step.name}' updated.")
            return redirect("designer_step_detail", plan_id=plan.pk, step_id=step.pk)
        messages.error(request, "Please correct the errors below.")
    else:
        form = ManufacturingStepForm(instance=step)
        checklist_formset = DesignerQualityChecklistFormSet(
            instance=step, prefix="quality"
        )
        material_formset = StepMaterialFormSet(instance=step, prefix="material")

    return render(
        request,
        "designer/step_form.html",
        {
            "plan": plan,
            "step": step,
            "form": form,
            "checklist_formset": checklist_formset,
            "material_formset": material_formset,
        },
    )


# ------------------------------------------------------------------
# Item reservations (BOM / warehouse catalog)
# ------------------------------------------------------------------


@designer_required
def item_reservation_list(request):
    reservations = ItemReservation.objects.order_by("name", "sku")
    return render(
        request,
        "designer/item_reservation_list.html",
        {"reservations": reservations},
    )


@designer_required
def item_reservation_create(request):
    if request.method == "POST":
        form = ItemReservationForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.created_by = request.user
            obj.save()
            messages.success(request, "Item reservation created.")
            return redirect("designer_item_reservation_list")
    else:
        form = ItemReservationForm()
    return render(
        request,
        "designer/item_reservation_form.html",
        {"form": form},
    )


# ------------------------------------------------------------------
# Delete a step
# ------------------------------------------------------------------


@designer_required
@require_POST
def delete_step(request, plan_id, step_id):
    plan = get_object_or_404(ManufacturingPlan, pk=plan_id)
    step = get_object_or_404(ManufacturingStep, pk=step_id, plan=plan)
    step_name = step.name
    step.delete()
    sync_warehouse_steps_from_bom(plan)
    messages.success(request, f"Step '{step_name}' deleted.")
    return redirect("designer_plan_editor", plan_id=plan.pk)


# ------------------------------------------------------------------
# Graph data JSON endpoint
# ------------------------------------------------------------------


@designer_required
def graph_data(request, plan_id):
    plan = get_object_or_404(ManufacturingPlan, pk=plan_id)
    steps = plan.steps.all()

    STATUS_COLORS = {
        "pending": "#6c757d",
        "in_progress": "#0d6efd",
        "completed": "#198754",
        "skipped": "#ffc107",
    }

    nodes = []
    for s in steps:
        nodes.append(
            {
                "id": s.pk,
                "label": s.name,
                "x": s.position_x,
                "y": s.position_y,
                "color": STATUS_COLORS.get(s.status, "#6c757d"),
                "status": s.status,
                "step_kind": s.step_kind,
            }
        )

    edges = []
    deps = StepDependency.objects.filter(from_step__plan=plan)
    for d in deps:
        edges.append(
            {
                "from": d.from_step_id,
                "to": d.to_step_id,
                "id": d.pk,
            }
        )

    return JsonResponse({"nodes": nodes, "edges": edges})


# ------------------------------------------------------------------
# Save graph — positions + edges with DAG validation
# ------------------------------------------------------------------


@designer_required
@require_POST
def save_graph(request, plan_id):
    plan = get_object_or_404(ManufacturingPlan, pk=plan_id)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON."}, status=400)

    err = save_graph_from_payload(plan, data)
    if err:
        return JsonResponse({"success": False, "error": err}, status=400)

    sync_warehouse_steps_from_bom(plan)

    return JsonResponse({"success": True})
