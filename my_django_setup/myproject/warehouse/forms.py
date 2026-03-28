from django import forms

from warehouse.models import ItemReservation


class StoredItemReceiveForm(forms.Form):
    item_reservation = forms.ModelChoiceField(
        queryset=ItemReservation.objects.order_by("name", "sku"),
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Item reservation (type)",
    )
    label = forms.CharField(
        required=False,
        max_length=200,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Batch / serial (optional)"}
        ),
    )


class WarehouseItemReservationForm(forms.ModelForm):
    class Meta:
        model = ItemReservation
        fields = ["name", "sku", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "sku": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }
