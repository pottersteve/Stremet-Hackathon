from django import forms
from django.forms import inlineformset_factory

from .models import (
    ManufacturingPlan, ManufacturingStep,
    QualityChecklistItem, StepMaterial,
)


class ManufacturingPlanForm(forms.ModelForm):
    class Meta:
        model = ManufacturingPlan
        fields = ['name', 'description', 'status']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }


_STEP_WIDGETS = {
    'name': forms.TextInput(attrs={'class': 'form-control'}),
    'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
    'sop_text': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
    'sop_document': forms.ClearableFileInput(attrs={'class': 'form-control'}),
    'status': forms.Select(attrs={'class': 'form-select'}),
    'estimated_duration_hours': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
}


class ManufacturingStepCreateForm(forms.ModelForm):
    """Add-step modal: sequence_order is set in the view, not posted from the form."""

    class Meta:
        model = ManufacturingStep
        fields = ['name', 'description', 'sop_document', 'sop_text', 'status', 'estimated_duration_hours']
        widgets = _STEP_WIDGETS


class ManufacturingStepForm(forms.ModelForm):
    class Meta:
        model = ManufacturingStep
        fields = [
            'name', 'description', 'sequence_order',
            'sop_document', 'sop_text', 'status',
            'estimated_duration_hours',
        ]
        widgets = {
            **_STEP_WIDGETS,
            'sequence_order': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class QualityChecklistItemForm(forms.ModelForm):
    class Meta:
        model = QualityChecklistItem
        fields = ['description', 'expected_result', 'result_status', 'notes']
        widgets = {
            'description': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'What to check'}),
            'expected_result': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Expected value/condition'}),
            'result_status': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Notes'}),
        }


class StepMaterialForm(forms.ModelForm):
    class Meta:
        model = StepMaterial
        fields = [
            'material_name', 'specification', 'quantity', 'unit',
            'supplier_notes', 'storage_location', 'storage_conditions',
        ]
        widgets = {
            'material_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. S355 Steel Sheet'}),
            'specification': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Grade, coating, etc.'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'unit': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'kg, sheets, m'}),
            'supplier_notes': forms.TextInput(attrs={'class': 'form-control'}),
            'storage_location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Warehouse A, Shelf B3'}),
            'storage_conditions': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Keep dry, max 25C'}),
        }


QualityChecklistFormSet = inlineformset_factory(
    ManufacturingStep, QualityChecklistItem,
    form=QualityChecklistItemForm,
    extra=1, can_delete=True,
)

StepMaterialFormSet = inlineformset_factory(
    ManufacturingStep, StepMaterial,
    form=StepMaterialForm,
    extra=1, can_delete=True,
)
