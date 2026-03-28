from django import forms
from django.forms import inlineformset_factory

from designer.models import ManufacturingStep, QualityChecklistItem


class StepProgressForm(forms.ModelForm):
    class Meta:
        model = ManufacturingStep
        fields = ['status', 'execution_notes']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'execution_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }


class ManufacturerQualityChecklistItemForm(forms.ModelForm):
    class Meta:
        model = QualityChecklistItem
        fields = ['result_status', 'notes']
        widgets = {
            'result_status': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Observations'}),
        }


ManufacturerQualityChecklistFormSet = inlineformset_factory(
    ManufacturingStep,
    QualityChecklistItem,
    form=ManufacturerQualityChecklistItemForm,
    extra=0,
    can_delete=False,
)
