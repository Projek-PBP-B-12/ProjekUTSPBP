from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from FoodItem.models import FoodItem
from Location.models import Location
from .models import SharedPost, SharedPostWriteQuota


@override_settings(SHAREDPOST_WRITE_LIMIT=2, SHAREDPOST_WRITE_WINDOW_SECONDS=60)
class SharedPostRateLimitTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username="limited_donor")
        cls.other = get_user_model().objects.create_user(username="separate_donor")
        cls.location = Location.objects.create(
            owner=cls.owner, area_name="Beji", latitude="-6.36", longitude="106.83",
        )
        cls.food = FoodItem.objects.create(
            owner=cls.owner, name="Roti", status="STORED", category="GRAIN",
            purchase_date=timezone.localdate(), expiration_date=timezone.localdate() + timedelta(days=3),
        )
        cls.offered = FoodItem.objects.create(
            owner=cls.owner, name="Susu", status="OFFERED", category="BEVERAGE",
            purchase_date=timezone.localdate(), expiration_date=timezone.localdate() + timedelta(days=3),
        )
        cls.post = SharedPost.objects.create(
            food_item=cls.offered, location=cls.location, description="Ambil di lobi sore hari.",
        )

    def setUp(self):
        self.client.force_login(self.owner)
        self.create_url = reverse("sharedpost:create")

    def payload(self, **overrides):
        return {
            "food_item": self.food.pk, "location": self.location.pk,
            "description": "Ambil di pos satpam sore hari.", **overrides,
        }

    def exhaust(self):
        for _ in range(2):
            self.assertEqual(self.client.post(self.create_url).status_code, 200)

    def test_one_budget_covers_create_update_delete_and_complete(self):
        created = self.client.post(self.create_url, self.payload())
        self.assertEqual(created.status_code, 302)
        post = SharedPost.objects.get(food_item=self.food)
        changed = self.client.post(
            reverse("sharedpost:update", args=[post.pk]),
            self.payload(description="Petunjuk pengambilan yang sudah diperbarui."),
        )
        self.assertEqual(changed.status_code, 302)
        for name in ["delete", "complete"]:
            with self.subTest(action=name):
                response = self.client.post(reverse(f"sharedpost:{name}", args=[post.pk]))
                self.assertEqual(response.status_code, 429)
        self.assertEqual(self.client.post(self.create_url, self.payload()).status_code, 429)
        post.refresh_from_db()
        self.food.refresh_from_db()
        self.assertTrue(post.is_active)
        self.assertEqual(post.description, "Petunjuk pengambilan yang sudah diperbarui.")
        self.assertEqual(self.food.status, "OFFERED")

    def test_rejected_htmx_mutations_have_retry_header_and_do_not_change_data(self):
        self.exhaust()
        for action in ["update", "delete", "complete"]:
            with self.subTest(action=action):
                response = self.client.post(
                    reverse(f"sharedpost:{action}", args=[self.post.pk]),
                    self.payload(description="Perubahan ini harus ditolak."), HTTP_HX_REQUEST="true",
                )
                self.assertEqual(response.status_code, 429)
                self.assertGreaterEqual(int(response["Retry-After"]), 1)
                self.assertLessEqual(int(response["Retry-After"]), 60)
                self.assertIn("no-store", response["Cache-Control"])
                self.assertNotIn("HX-Trigger", response.headers)
                self.assertNotIn("X-SharedPost-Action", response.headers)
                self.assertContains(response, "Batas perubahan tercapai", status_code=429)
        self.post.refresh_from_db()
        self.offered.refresh_from_db()
        self.assertTrue(self.post.is_active)
        self.assertEqual(self.post.description, "Ambil di lobi sore hari.")
        self.assertEqual(self.offered.status, "OFFERED")
        self.assertEqual(SharedPostWriteQuota.objects.get(user=self.owner).request_count, 2)

    def test_retry_after_and_budget_reset_at_the_window_boundary(self):
        start = timezone.now().replace(microsecond=0)
        with patch("SharedPost.decorators.timezone.now", return_value=start):
            self.exhaust()
        with patch("SharedPost.decorators.timezone.now", return_value=start + timedelta(seconds=59)):
            response = self.client.post(self.create_url)
            self.assertEqual(response.status_code, 429)
            self.assertEqual(response["Retry-After"], "1")
        with patch("SharedPost.decorators.timezone.now", return_value=start + timedelta(seconds=60)):
            self.assertEqual(self.client.post(self.create_url).status_code, 200)
        quota = SharedPostWriteQuota.objects.get(user=self.owner)
        self.assertEqual(quota.request_count, 1)
        self.assertEqual(quota.window_started_at, start + timedelta(seconds=60))

    def test_budget_is_per_account_and_survives_a_new_session(self):
        self.exhaust()
        second_session = Client()
        second_session.force_login(self.owner)
        self.assertEqual(second_session.post(self.create_url).status_code, 429)
        self.client.logout()
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(self.create_url).status_code, 429)
        second_session.force_login(self.other)
        self.assertEqual(second_session.post(self.create_url).status_code, 200)
        self.assertEqual(SharedPostWriteQuota.objects.get(user=self.other).request_count, 1)

    def test_changing_record_ids_or_forwarded_ip_headers_does_not_bypass_budget(self):
        self.exhaust()
        for pk, address in [(self.post.pk, "192.0.2.1"), (999999, "198.51.100.2")]:
            response = self.client.post(
                reverse("sharedpost:delete", args=[pk]), HTTP_X_FORWARDED_FOR=address,
                REMOTE_ADDR=address,
            )
            self.assertEqual(response.status_code, 429)
        self.assertTrue(SharedPost.objects.filter(pk=self.post.pk).exists())

    def test_read_requests_remain_available_and_do_not_consume_budget(self):
        for name, args in [("list", []), ("detail", [self.post.pk]), ("create", []), ("update", [self.post.pk])]:
            self.assertEqual(self.client.get(reverse(f"sharedpost:{name}", args=args)).status_code, 200)
        self.assertFalse(SharedPostWriteQuota.objects.filter(user=self.owner).exists())
        self.exhaust()
        for name, args in [("list", []), ("detail", [self.post.pk]), ("create", []), ("update", [self.post.pk])]:
            self.assertEqual(self.client.get(reverse(f"sharedpost:{name}", args=args)).status_code, 200)
        self.assertEqual(SharedPostWriteQuota.objects.get(user=self.owner).request_count, 2)

    def test_anonymous_csrf_and_disallowed_methods_do_not_consume_budget(self):
        self.assertEqual(Client().post(self.create_url).status_code, 302)
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.owner)
        self.assertEqual(protected.post(self.create_url, self.payload()).status_code, 403)
        for action in ["delete", "complete"]:
            self.assertEqual(self.client.get(reverse(f"sharedpost:{action}", args=[self.post.pk])).status_code, 405)
        self.assertFalse(SharedPostWriteQuota.objects.exists())

    def test_view_rollback_does_not_refund_the_attempt(self):
        with patch("FoodItem.models.FoodItem.save", side_effect=RuntimeError("Inventory update failed")):
            with self.assertRaises(RuntimeError):
                self.client.post(self.create_url, self.payload())
        self.assertFalse(SharedPost.objects.filter(food_item=self.food).exists())
        self.food.refresh_from_db()
        self.assertEqual(self.food.status, "STORED")
        self.assertEqual(SharedPostWriteQuota.objects.get(user=self.owner).request_count, 1)
        self.assertEqual(self.client.post(self.create_url).status_code, 200)
        self.assertEqual(self.client.post(self.create_url).status_code, 429)

    @override_settings(SHAREDPOST_WRITE_LIMIT=0)
    def test_invalid_configuration_does_not_silently_disable_protection(self):
        with self.assertRaises(ImproperlyConfigured):
            self.client.post(self.create_url, self.payload())
        self.assertFalse(SharedPost.objects.filter(food_item=self.food).exists())
