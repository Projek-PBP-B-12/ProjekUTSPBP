from django.db import migrations
from django.utils import timezone


def reconcile_offer_status(apps, schema_editor):
    """Repair states left by the previous independent inventory status endpoints."""
    Food = apps.get_model("FoodItem", "FoodItem")
    Post = apps.get_model("SharedPost", "SharedPost")
    database = schema_editor.connection.alias
    now = timezone.now()
    Post.objects.using(database).filter(is_active=True).exclude(
        food_item__status="OFFERED",
    ).update(is_active=False, updated_at=now)
    Food.objects.using(database).filter(status="OFFERED").exclude(
        shared_posts__is_active=True,
    ).update(status="STORED", updated_at=now)


class Migration(migrations.Migration):
    dependencies = [
        ("SharedPost", "0002_location_restrict"),
        ("FoodItem", "0005_alter_fooditem_status"),
    ]

    # Rollback must not republish old offers or guess which prior states were intentional.
    operations = [migrations.RunPython(reconcile_offer_status, migrations.RunPython.noop)]
