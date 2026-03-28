from django.contrib import messages
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from designer.models import ManufacturingPlan, ManufacturingStep
from home.permissions import manufacturer_required

from .forms import ManufacturerQualityChecklistFormSet, StepProgressForm
from .services import manufacturer_orders_queryset, plan_work_summary


def _order_in_mfg_queue_or_404(order_id):
    qs = manufacturer_orders_queryset()
    return get_object_or_404(qs, pk=order_id)


def _step_in_mfg_queue_or_404(plan_id, step_id):
    step = get_object_or_404(ManufacturingStep, pk=step_id, plan_id=plan_id)
    plan = step.plan
    if plan.status not in ("ready", "approved") or plan.order.status == "delivered":
        raise Http404()
    return step


def _apply_step_timestamps(step, old_status, new_status):
    now = timezone.now()
    if (
        new_status == "in_progress"
        and old_status != "in_progress"
        and step.started_at is None
    ):
        step.started_at = now
    if new_status in ("completed", "skipped") and old_status not in (
        "completed",
        "skipped",
    ):
        step.completed_at = now


@manufacturer_required
def manufacturer_dashboard(request):
    search = request.GET.get("q", "").strip()
    orders = manufacturer_orders_queryset()
    if search:
        orders = orders.filter(
            Q(order_id__icontains=search) | Q(client__company_name__icontains=search)
        ).distinct()

    rows = []
    for order in orders:
        summary = plan_work_summary(order.manufacturing_plan)
        rows.append({"order": order, **summary})

    return render(
        request,
        "manufacturer/dashboard.html",
        {
            "rows": rows,
            "search_query": search,
        },
    )


@manufacturer_required
def order_execution(request, order_id):
    order = _order_in_mfg_queue_or_404(order_id)
    plan = order.manufacturing_plan
    summary = plan_work_summary(plan)
    steps = plan.steps.all()

    return render(
        request,
        "manufacturer/order_execution.html",
        {
            "order": order,
            "plan": plan,
            "steps": steps,
            **summary,
        },
    )


@manufacturer_required
def step_execution(request, plan_id, step_id):
    step = _step_in_mfg_queue_or_404(plan_id, step_id)
    plan = step.plan
    order = plan.order

    if request.method == "POST":
        old_status = step.status
        progress_form = StepProgressForm(request.POST, instance=step)
        checklist_formset = ManufacturerQualityChecklistFormSet(
            request.POST, instance=step, prefix="qc"
        )
        if progress_form.is_valid() and checklist_formset.is_valid():
            step_obj = progress_form.save(commit=False)
            if request.POST.get("complete_and_next"):
                new_status = "completed"
                step_obj.status = new_status
            else:
                new_status = step_obj.status
            _apply_step_timestamps(step_obj, old_status, new_status)
            step_obj.save()
            checklist_formset.save()

            if request.POST.get("complete_and_next"):
                plan_fresh = ManufacturingPlan.objects.prefetch_related(
                    "steps__incoming_dependencies__from_step"
                ).get(pk=plan.pk)
                summary = plan_work_summary(plan_fresh)
                nxt = summary["primary_step"]
                messages.success(
                    request,
                    "Step marked complete. Quality report saved."
                    if nxt
                    else "Step marked complete. No further actionable steps on this plan.",
                )
                if nxt:
                    return redirect(
                        "manufacturer_step_execution",
                        plan_id=plan.pk,
                        step_id=nxt.pk,
                    )
                return redirect("manufacturer_order_execution", order_id=order.pk)

            messages.success(request, "Step progress and quality report saved.")
            return redirect(
                "manufacturer_step_execution", plan_id=plan.pk, step_id=step.pk
            )
        messages.error(request, "Please correct the errors below.")
    else:
        progress_form = StepProgressForm(instance=step)
        checklist_formset = ManufacturerQualityChecklistFormSet(
            instance=step, prefix="qc"
        )

    preds = list(step.incoming_dependencies.select_related("from_step").all())

    return render(
        request,
        "manufacturer/step_execution.html",
        {
            "order": order,
            "plan": plan,
            "step": step,
            "progress_form": progress_form,
            "checklist_formset": checklist_formset,
            "predecessors": preds,
        },
    )
