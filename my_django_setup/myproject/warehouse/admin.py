from django.contrib import admin

from .models import ItemReservation, StorageSpace, StoredItem


@admin.register(ItemReservation)
class ItemReservationAdmin(admin.ModelAdmin):
    list_display = ("name", "sku", "created_at")
    search_fields = ("name", "sku")


@admin.register(StorageSpace)
class StorageSpaceAdmin(admin.ModelAdmin):
    list_display = ("slot_number",)


@admin.register(StoredItem)
class StoredItemAdmin(admin.ModelAdmin):
    list_display = ("item_reservation", "storage_space", "stored_at")
    list_filter = ("item_reservation",)
