from django.contrib.auth.models import User
from django.db import models


class ManufacturingPlan(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("ready", "Ready"),
        ("approved", "Approved"),
    ]

    order = models.OneToOneField(
        "home.Order", on_delete=models.CASCADE, related_name="manufacturing_plan"
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    designer = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="manufacturing_plans"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} (Order: {self.order.order_id})"


class ManufacturingStep(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("skipped", "Skipped"),
    ]

    STEP_KIND_MANUFACTURING = "manufacturing"
    STEP_KIND_WAREHOUSE_PICKUP = "warehouse_pickup"
    STEP_KIND_CHOICES = [
        (STEP_KIND_MANUFACTURING, "Manufacturing"),
        (STEP_KIND_WAREHOUSE_PICKUP, "Warehouse pickup"),
    ]

    plan = models.ForeignKey(
        ManufacturingPlan, on_delete=models.CASCADE, related_name="steps"
    )
    step_kind = models.CharField(
        max_length=32,
        choices=STEP_KIND_CHOICES,
        default=STEP_KIND_MANUFACTURING,
    )
    picks_for = models.OneToOneField(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="warehouse_pickup_step",
        help_text="Manufacturing step whose BOM drives this pickup (pickup steps only).",
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    sequence_order = models.PositiveIntegerField(default=0)
    sop_document = models.FileField(upload_to="designer/sops/", blank=True, null=True)
    sop_text = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    estimated_duration_hours = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True
    )
    position_x = models.FloatField(default=0)
    position_y = models.FloatField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    execution_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["sequence_order"]

    def __str__(self):
        return f"{self.name} (Plan: {self.plan.name})"


class QualityChecklistItem(models.Model):
    RESULT_CHOICES = [
        ("pending", "Pending"),
        ("pass", "Pass"),
        ("fail", "Fail"),
        ("na", "Not Applicable"),
    ]

    step = models.ForeignKey(
        ManufacturingStep, on_delete=models.CASCADE, related_name="quality_checklist"
    )
    description = models.CharField(max_length=500)
    expected_result = models.CharField(max_length=300, blank=True)
    result_status = models.CharField(
        max_length=20, choices=RESULT_CHOICES, default="pending"
    )
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.description[:50]} ({self.get_result_status_display()})"


class StepMaterial(models.Model):
    step = models.ForeignKey(
        ManufacturingStep, on_delete=models.CASCADE, related_name="materials"
    )
    item_reservation = models.ForeignKey(
        "warehouse.ItemReservation",
        on_delete=models.PROTECT,
        related_name="bom_lines",
    )
    material_name = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text="Deprecated display cache; use item_reservation.name.",
    )
    specification = models.TextField(blank=True)
    quantity = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    unit = models.CharField(max_length=50, blank=True)
    supplier_notes = models.TextField(blank=True)
    storage_location = models.CharField(
        max_length=300,
        blank=True,
        help_text="Current location, e.g. 'Warehouse A, Shelf B3'",
    )
    storage_conditions = models.CharField(
        max_length=300,
        blank=True,
        help_text="Special requirements, e.g. 'Keep dry, max 25C'",
    )

    def save(self, *args, **kwargs):
        if self.item_reservation_id:
            self.material_name = self.item_reservation.name
        super().save(*args, **kwargs)

    def __str__(self):
        label = (
            self.item_reservation.name
            if self.item_reservation_id
            else self.material_name
        )
        return f"{label} ({self.quantity or '?'} {self.unit})"


class StepDependency(models.Model):
    from_step = models.ForeignKey(
        ManufacturingStep,
        on_delete=models.CASCADE,
        related_name="outgoing_dependencies",
    )
    to_step = models.ForeignKey(
        ManufacturingStep,
        on_delete=models.CASCADE,
        related_name="incoming_dependencies",
    )

    class Meta:
        unique_together = ("from_step", "to_step")
        verbose_name_plural = "Step dependencies"

    def __str__(self):
        return f"{self.from_step.name} -> {self.to_step.name}"
