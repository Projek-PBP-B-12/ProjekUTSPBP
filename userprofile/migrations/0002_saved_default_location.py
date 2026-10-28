from django.db import migrations, models
import django.db.models.deletion


def copy_coordinates_to_locations(apps, schema_editor):
    Profile = apps.get_model("userprofile", "UserProfile")
    Location = apps.get_model("Location", "Location")
    database = schema_editor.connection.alias
    profiles = Profile.objects.using(database).filter(
        default_latitude__isnull=False, default_longitude__isnull=False
    )
    for profile in profiles.iterator():
        # Reuse an owned location at exactly the saved point if one already exists.
        location = Location.objects.using(database).filter(
            owner_id=profile.user_id,
            latitude=profile.default_latitude,
            longitude=profile.default_longitude,
        ).order_by("pk").first()
        if location is None:
            location = Location.objects.using(database).create(
                owner_id=profile.user_id,
                area_name="Lokasi utama",
                latitude=profile.default_latitude,
                longitude=profile.default_longitude,
            )
        Profile.objects.using(database).filter(pk=profile.pk).update(
            default_location_id=location.pk
        )


def restore_coordinates(apps, schema_editor):
    Profile = apps.get_model("userprofile", "UserProfile")
    database = schema_editor.connection.alias
    for profile in Profile.objects.using(database).select_related("default_location").iterator():
        if profile.default_location_id:
            Profile.objects.using(database).filter(pk=profile.pk).update(
                default_latitude=profile.default_location.latitude,
                default_longitude=profile.default_location.longitude,
            )
    # Saved locations are retained: they may also be used by a food offer.


class Migration(migrations.Migration):
    dependencies = [
        ("userprofile", "0001_initial"),
        ("Location", "0002_location_owner_alter_location_latitude_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="default_location",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="default_for_profiles",
                to="Location.location",
                verbose_name="Lokasi bawaan",
            ),
        ),
        migrations.RunPython(copy_coordinates_to_locations, restore_coordinates),
        migrations.RemoveConstraint(model_name="userprofile", name="profile_coordinates_pair"),
        migrations.RemoveConstraint(model_name="userprofile", name="profile_latitude_range"),
        migrations.RemoveConstraint(model_name="userprofile", name="profile_longitude_range"),
        migrations.RemoveField(model_name="userprofile", name="default_latitude"),
        migrations.RemoveField(model_name="userprofile", name="default_longitude"),
    ]
