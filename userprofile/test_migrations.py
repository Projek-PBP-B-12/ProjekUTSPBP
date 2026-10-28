"""Koordinat profil lama tidak hilang saat beralih ke lokasi tersimpan."""

from decimal import Decimal

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class SavedLocationMigrationTests(TransactionTestCase):
    migrate_from = [("userprofile", "0001_initial")]
    migrate_to = [("userprofile", "0002_saved_default_location")]

    def setUp(self):
        executor = MigrationExecutor(connection)
        self.latest_targets = executor.loader.graph.leaf_nodes()
        self.addCleanup(self.restore_latest_schema)
        executor.migrate(self.migrate_from)
        self.old_apps = executor.loader.project_state([
            ("userprofile", "0001_initial"),
            ("Location", "0002_location_owner_alter_location_latitude_and_more"),
        ]).apps

    def restore_latest_schema(self):
        MigrationExecutor(connection).migrate(self.latest_targets)

    def test_upgrade_reuses_owned_point_preserves_zero_and_can_restore_coordinates(self):
        User = self.old_apps.get_model("auth", "User")
        Profile = self.old_apps.get_model("userprofile", "UserProfile")
        Location = self.old_apps.get_model("Location", "Location")
        owner = User.objects.create(username="migrasi_lama", email="")
        second = User.objects.create(username="migrasi_kedua")
        empty = User.objects.create(username="migrasi_tanpa_lokasi")
        own_location = Location.objects.create(owner_id=owner.pk, area_name="Rumah", latitude=Decimal("-6.360000"), longitude=Decimal("106.820000"))
        # A same-point location owned by somebody else must not become the default.
        foreign_location = Location.objects.create(owner_id=owner.pk, area_name="Titik nol", latitude=0, longitude=0)
        Profile.objects.create(user_id=owner.pk, default_latitude=own_location.latitude, default_longitude=own_location.longitude)
        Profile.objects.create(user_id=second.pk, default_latitude=0, default_longitude=0)
        Profile.objects.create(user_id=empty.pk)

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        apps = executor.loader.project_state(self.migrate_to).apps
        NewProfile = apps.get_model("userprofile", "UserProfile")
        NewLocation = apps.get_model("Location", "Location")
        self.assertEqual(NewProfile.objects.get(user_id=owner.pk).default_location_id, own_location.pk)
        copied = NewProfile.objects.get(user_id=second.pk).default_location
        self.assertNotEqual(copied.pk, foreign_location.pk)
        self.assertEqual(copied.owner_id, second.pk)
        self.assertEqual(copied.area_name, "Lokasi utama")
        self.assertEqual((copied.latitude, copied.longitude), (Decimal("0"), Decimal("0")))
        self.assertIsNone(NewProfile.objects.get(user_id=empty.pk).default_location_id)
        self.assertEqual(NewLocation.objects.count(), 3)
        self.assertEqual(apps.get_model("auth", "User").objects.get(pk=owner.pk).email, "")

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        restored = self.old_apps.get_model("userprofile", "UserProfile")
        legacy = restored.objects.get(user_id=owner.pk)
        self.assertEqual((legacy.default_latitude, legacy.default_longitude), (Decimal("-6.360000"), Decimal("106.820000")))
        legacy_zero = restored.objects.get(user_id=second.pk)
        self.assertEqual((legacy_zero.default_latitude, legacy_zero.default_longitude), (Decimal("0"), Decimal("0")))
        self.assertEqual(Location.objects.count(), 3)
