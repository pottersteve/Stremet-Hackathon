# Data migration: extend warehouse from 100 to 200 slots.

from django.db import migrations


def add_slots_101_200(apps, schema_editor):
    StorageSpace = apps.get_model("warehouse", "StorageSpace")
    existing = set(StorageSpace.objects.values_list("slot_number", flat=True))
    to_create = [
        StorageSpace(slot_number=i)
        for i in range(101, 201)
        if i not in existing
    ]
    if to_create:
        StorageSpace.objects.bulk_create(to_create)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("warehouse", "0002_alter_storeditem_label"),
    ]

    operations = [
        migrations.RunPython(add_slots_101_200, noop_reverse),
    ]
