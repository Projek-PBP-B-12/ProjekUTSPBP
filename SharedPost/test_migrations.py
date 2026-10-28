from datetime import timedelta

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class LegacyOfferMigrationTests(TransactionTestCase):
    migrate_from = [
        ("SharedPost", "0002_location_restrict"),
        ("FoodItem", "0005_alter_fooditem_status"),
    ]
    migrate_to = [("SharedPost", "0003_reconcile_legacy_offer_status")]

    def setUp(self):
        executor = MigrationExecutor(connection)
        self.latest_targets = executor.loader.graph.leaf_nodes()
        self.addCleanup(self.restore_latest_schema)
        executor.migrate(self.migrate_from)
        self.old_apps = executor.loader.project_state(self.migrate_from + [
            ("Location", "0002_location_owner_alter_location_latitude_and_more"),
        ]).apps

    def restore_latest_schema(self):
        MigrationExecutor(connection).migrate(self.latest_targets)

    def test_repair_closes_inconsistent_offers_without_republishing_or_deleting_history(self):
        User = self.old_apps.get_model("auth", "User")
        Location = self.old_apps.get_model("Location", "Location")
        Food = self.old_apps.get_model("FoodItem", "FoodItem")
        Post = self.old_apps.get_model("SharedPost", "SharedPost")
        today = timezone.localdate()
        owner = User.objects.create(username="legacy-donor", email="legacy@example.com")
        other = User.objects.create(username="second-donor", email="other@example.com")
        home = Location.objects.create(owner_id=owner.pk, area_name="Rumah", latitude="-6.361234", longitude="106.821234")
        campus = Location.objects.create(owner_id=other.pk, area_name="Kampus", latitude="-6.362345", longitude="106.822345")

        def make_food(name, status, *, user=owner, expired=False):
            return Food.objects.create(
                owner_id=user.pk, name=name, status=status,
                purchase_date=today - timedelta(days=3),
                expiration_date=today + timedelta(days=-1 if expired else 3),
            )

        def make_post(food, *, active=True, location=home):
            return Post.objects.create(
                food_item_id=food.pk, location_id=location.pk, is_active=active,
                description="Ambil di gerbang setelah menghubungi donor.",
            )

        stored = make_food("Stored with stale offer", "STORED")
        consumed = make_food("Consumed with stale offer", "CONSUMED")
        stale_stored = make_post(stored)
        stale_consumed = make_post(consumed)
        orphan = make_food("Offered without post", "OFFERED")
        historical = make_food("Offered with inactive history", "OFFERED")
        old_post = make_post(historical, active=False)
        valid_food = make_food("Available food", "OFFERED")
        valid_post = make_post(valid_food)
        expired_food = make_food("Naturally expired offer", "OFFERED", expired=True)
        expired_post = make_post(expired_food)
        other_food = make_food("Other donor available food", "OFFERED", user=other)
        other_post = make_post(other_food, location=campus)

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        apps = executor.loader.project_state(self.migrate_to).apps
        NewFood = apps.get_model("FoodItem", "FoodItem")
        NewPost = apps.get_model("SharedPost", "SharedPost")
        self.assertEqual(NewFood.objects.get(pk=stored.pk).status, "STORED")
        self.assertEqual(NewFood.objects.get(pk=consumed.pk).status, "CONSUMED")
        for food in (orphan, historical):
            self.assertEqual(NewFood.objects.get(pk=food.pk).status, "STORED")
        for post in (stale_stored, stale_consumed, old_post):
            self.assertFalse(NewPost.objects.get(pk=post.pk).is_active)
        for food, post in ((valid_food, valid_post), (expired_food, expired_post), (other_food, other_post)):
            self.assertEqual(NewFood.objects.get(pk=food.pk).status, "OFFERED")
            self.assertTrue(NewPost.objects.get(pk=post.pk).is_active)
        self.assertEqual(NewFood.objects.count(), 7)
        self.assertEqual(NewPost.objects.count(), 6)
        self.assertEqual(Location.objects.count(), 2)
        self.assertEqual(User.objects.get(pk=owner.pk).email, "legacy@example.com")

        # Reversal retains the repair: an obsolete offer must not become public again.
        MigrationExecutor(connection).migrate(self.migrate_from)
        self.assertFalse(Post.objects.get(pk=stale_stored.pk).is_active)
        self.assertEqual(Food.objects.get(pk=orphan.pk).status, "STORED")
