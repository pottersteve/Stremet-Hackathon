from django.conf import settings
from django.db import models


class ItemReservation(models.Model):
    """Catalog type used by BOM lines (designer + warehouse can create)."""

    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_item_reservations",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.sku or self.name


class StorageSpace(models.Model):
    """Fixed slot 1..100; at most one StoredItem at a time."""

    slot_number = models.PositiveIntegerField(unique=True, db_index=True)

    class Meta:
        ordering = ["slot_number"]

    def __str__(self):
        return f"Slot {self.slot_number}"


class StoredItem(models.Model):
    """One physical unit in one slot, typed by ItemReservation."""

    item_reservation = models.ForeignKey(
        ItemReservation,
        on_delete=models.PROTECT,
        related_name="stored_items",
    )
    storage_space = models.OneToOneField(
        StorageSpace,
        on_delete=models.CASCADE,
        related_name="stored_item",
    )
    label = models.CharField(
        max_length=200,
        blank=True,
        help_text="Optional batch or serial label",
    )
    stored_at = models.DateTimeField(auto_now_add=True)
    stored_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="stored_warehouse_items",
    )

    class Meta:
        ordering = ["storage_space__slot_number"]

    def __str__(self):
        return f"{self.item_reservation} @ {self.storage_space}"
