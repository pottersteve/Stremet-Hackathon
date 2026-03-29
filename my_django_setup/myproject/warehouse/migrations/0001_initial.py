import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def seed_storage_spaces(apps, schema_editor):
    StorageSpace = apps.get_model("warehouse", "StorageSpace")
    StorageSpace.objects.bulk_create(
        [StorageSpace(slot_number=i) for i in range(1, 101)]
    )


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ItemReservation",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=200)),
                ("sku", models.CharField(blank=True, max_length=100)),
                ("description", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_item_reservations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="StorageSpace",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("slot_number", models.PositiveIntegerField(db_index=True, unique=True)),
            ],
            options={
                "ordering": ["slot_number"],
            },
        ),
        migrations.CreateModel(
            name="StoredItem",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("label", models.CharField(blank=True, max_length=200)),
                ("stored_at", models.DateTimeField(auto_now_add=True)),
                (
                    "item_reservation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="stored_items",
                        to="warehouse.itemreservation",
                    ),
                ),
                (
                    "storage_space",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="stored_item",
                        to="warehouse.storagespace",
                    ),
                ),
                (
                    "stored_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="stored_warehouse_items",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["storage_space__slot_number"],
            },
        ),
        migrations.RunPython(seed_storage_spaces, migrations.RunPython.noop),
    ]
