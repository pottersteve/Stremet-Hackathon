import django.db.models.deletion
from django.db import migrations, models


def backfill_item_reservations(apps, schema_editor):
    ItemReservation = apps.get_model("warehouse", "ItemReservation")
    StepMaterial = apps.get_model("designer", "StepMaterial")
    legacy, _ = ItemReservation.objects.get_or_create(
        sku="LEGACY",
        defaults={
            "name": "Legacy material — assign item reservation in designer",
            "description": "",
        },
    )
    for sm in StepMaterial.objects.all():
        sm.item_reservation_id = legacy.pk
        if not sm.material_name:
            sm.material_name = legacy.name
        sm.save(update_fields=["item_reservation_id", "material_name"])


class Migration(migrations.Migration):

    dependencies = [
        ("warehouse", "0001_initial"),
        ("designer", "0002_manufacturingstep_execution_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="manufacturingstep",
            name="step_kind",
            field=models.CharField(
                choices=[
                    ("manufacturing", "Manufacturing"),
                    ("warehouse_pickup", "Warehouse pickup"),
                ],
                default="manufacturing",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="manufacturingstep",
            name="picks_for",
            field=models.OneToOneField(
                blank=True,
                help_text="Manufacturing step whose BOM drives this pickup (pickup steps only).",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="warehouse_pickup_step",
                to="designer.manufacturingstep",
            ),
        ),
        migrations.AddField(
            model_name="stepmaterial",
            name="item_reservation",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="bom_lines",
                to="warehouse.itemreservation",
            ),
        ),
        migrations.AlterField(
            model_name="stepmaterial",
            name="material_name",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Deprecated display cache; use item_reservation.name.",
                max_length=200,
            ),
        ),
        migrations.RunPython(backfill_item_reservations, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="stepmaterial",
            name="item_reservation",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="bom_lines",
                to="warehouse.itemreservation",
            ),
        ),
    ]
