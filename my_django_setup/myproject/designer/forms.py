from django import forms
from django.forms import inlineformset_factory

from warehouse.models import ItemReservation

from .models import (
    ManufacturingPlan,
    ManufacturingStep,
    QualityChecklistItem,
    StepMaterial,
)


class ManufacturingPlanForm(forms.ModelForm):
    class Meta:
        model = ManufacturingPlan
        fields = ["name", "description", "status"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }


_STEP_WIDGETS = {
    "name": forms.TextInput(attrs={"class": "form-control"}),
    "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    "sop_text": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
    "sop_document": forms.ClearableFileInput(attrs={"class": "form-control"}),
    "status": forms.Select(attrs={"class": "form-select"}),
    "estimated_duration_hours": forms.NumberInput(
        attrs={"class": "form-control", "step": "0.1"}
    ),
}


class ManufacturingStepCreateForm(forms.ModelForm):
    """Add-step modal: sequence_order is set in the view, not posted from the form."""

    class Meta:
        model = ManufacturingStep
        fields = [
            "name",
            "description",
            "sop_document",
            "sop_text",
            "status",
            "estimated_duration_hours",
        ]
        widgets = _STEP_WIDGETS


class ManufacturingStepForm(forms.ModelForm):
    class Meta:
        model = ManufacturingStep
        fields = [
            "name",
            "description",
            "sequence_order",
            "sop_document",
            "sop_text",
            "status",
            "estimated_duration_hours",
        ]
        widgets = {
            **_STEP_WIDGETS,
            "sequence_order": forms.NumberInput(attrs={"class": "form-control"}),
        }


class DesignerQualityChecklistItemForm(forms.ModelForm):
    """Designer defines checks only; pass/fail is logged on the shop floor."""

    class Meta:
        model = QualityChecklistItem
        fields = ["description", "expected_result"]
        widgets = {
            "description": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "What to check"}
            ),
            "expected_result": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Expected value/condition",
                }
            ),
        }


class QualityChecklistItemForm(forms.ModelForm):
    class Meta:
        model = QualityChecklistItem
        fields = ["description", "expected_result", "result_status", "notes"]
        widgets = {
            "description": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "What to check"}
            ),
            "expected_result": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Expected value/condition",
                }
            ),
            "result_status": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Notes"}
            ),
        }


class StepMaterialForm(forms.ModelForm):
    class Meta:
        model = StepMaterial
        fields = [
            "item_reservation",
            "specification",
            "quantity",
            "unit",
            "supplier_notes",
            "storage_conditions",
        ]
        widgets = {
            "item_reservation": forms.Select(attrs={"class": "form-select"}),
            "specification": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Grade, coating, etc."}
            ),
            "quantity": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
            "unit": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "kg, sheets, m"}
            ),
            "supplier_notes": forms.TextInput(attrs={"class": "form-control"}),
            "storage_conditions": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Keep dry, max 25C"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["item_reservation"].queryset = ItemReservation.objects.order_by(
            "name", "sku"
        )
        self.fields["item_reservation"].label = "Item reservation (warehouse type)"


class ItemReservationForm(forms.ModelForm):
    class Meta:
        model = ItemReservation
        fields = ["name", "sku", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "sku": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }


DesignerQualityChecklistFormSet = inlineformset_factory(
    ManufacturingStep,
    QualityChecklistItem,
    form=DesignerQualityChecklistItemForm,
    extra=1,
    can_delete=True,
)

QualityChecklistFormSet = inlineformset_factory(
    ManufacturingStep,
    QualityChecklistItem,
    form=QualityChecklistItemForm,
    extra=1,
    can_delete=True,
)

StepMaterialFormSet = inlineformset_factory(
    ManufacturingStep,
    StepMaterial,
    form=StepMaterialForm,
    extra=1,
    can_delete=True,
)
