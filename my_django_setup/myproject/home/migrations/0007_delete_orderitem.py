# Generated manually for plan: remove legacy OrderItem

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0006_alter_userprofile_role"),
    ]

    operations = [
        migrations.DeleteModel(
            name="OrderItem",
        ),
    ]
