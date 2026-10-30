from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from Location.models import Location
from SharedPost.models import SharedPost
from notification.models import Notification
from userprofile.models import UserProfile
from .models import FoodItem


class InventoryIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username="inventory-owner", email="owner@example.com")
        cls.other = get_user_model().objects.create_user(username="inventory-other", email="other@example.com")
        cls.location = Location.objects.create(owner=cls.owner, area_name="Rumah", latitude="-6.360123", longitude="106.830123")
        cls.profile = UserProfile.objects.create(user=cls.owner, default_location=cls.location)
        cls.food = FoodItem.objects.create(
            owner=cls.owner, name="Roti gandum", category="GRAIN", status="STORED",
            purchase_date=timezone.localdate() - timedelta(days=2),
            expiration_date=timezone.localdate() + timedelta(days=3),
        )
        cls.other_food = FoodItem.objects.create(
            owner=cls.other, name="Makanan pribadi orang lain", category="OTHER",
            purchase_date=timezone.localdate(), expiration_date=timezone.localdate() + timedelta(days=3),
        )

    def setUp(self):
        self.client.force_login(self.owner)

    def publish(self):
        response = self.client.post(reverse("sharedpost:create"), {
            "food_item": self.food.pk, "location": self.location.pk,
            "description": "Ambil di depan gerbang pada sore hari.",
        })
        self.assertEqual(response.status_code, 302)
        return SharedPost.objects.get(food_item=self.food, is_active=True)

    def food_data(self, **changes):
        data = {
            "name": self.food.name, "category": self.food.category,
            "purchase_date": str(self.food.purchase_date), "expiration_date": str(self.food.expiration_date),
            "image_url": "",
        }
        data.update(changes)
        return data

    def test_inventory_is_private_searchable_and_links_to_publication(self):
        response = self.client.get(reverse("FoodItem:list_food_items"))
        self.assertContains(response, self.food.name)
        self.assertNotContains(response, self.other_food.name)
        self.assertContains(response, reverse("sharedpost:create") + f"?food={self.food.pk}")
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertNotContains(self.client.get(reverse("FoodItem:list_food_items"), {"q": "absent"}), self.food.name)

    def test_anonymous_pages_and_api_require_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("FoodItem:list_food_items")).status_code, 302)
        self.assertEqual(self.client.get(reverse("FoodItem:get_food_items")).status_code, 401)
        self.assertEqual(self.client.post(reverse("FoodItem:make_food_item_status_consumed", args=[self.food.pk])).status_code, 401)

    def test_add_food_uses_session_owner_and_cannot_forge_offered_status(self):
        response = self.client.post(reverse("FoodItem:add_food_item"), self.food_data(
            name="Apel baru", owner=self.other.pk, status="OFFERED",
        ))
        self.assertRedirects(response, reverse("FoodItem:list_food_items"))
        food = FoodItem.objects.get(name="Apel baru")
        self.assertEqual(food.owner, self.owner)
        self.assertEqual(food.status, "STORED")

    def test_empty_and_malformed_forms_show_errors_without_500(self):
        url = reverse("FoodItem:add_food_item")
        response = self.client.post(url, {})
        self.assertTrue(response.context["form"].is_bound)
        self.assertIn("name", response.context["form"].errors)
        for field in ("purchase_date", "expiration_date"):
            response = self.client.post(url, self.food_data(**{field: "not-a-date"}))
            self.assertEqual(response.status_code, 200)
            self.assertIn(field, response.context["form"].errors)
        response = self.client.post(url, self.food_data(expiration_date=str(self.food.purchase_date - timedelta(days=1))))
        self.assertContains(response, "Expiration date cannot be before purchase date.")
        self.assertEqual(FoodItem.objects.count(), 2)

    def test_photo_url_validation_preserves_existing_food_on_invalid_edit(self):
        for route in (reverse("FoodItem:add_food_item"), reverse("FoodItem:change_food_item", args=[self.food.pk])):
            for url in ("ftp://example.com/photo.jpg", "javascript:alert(1)", "data:image/png;base64,abc"):
                with self.subTest(route=route, url=url):
                    response = self.client.post(route, self.food_data(name="Tidak boleh tersimpan", image_url=url))
                    self.assertEqual(response.status_code, 200)
                    self.assertIn("image_url", response.context["form"].errors)
        self.food.refresh_from_db()
        self.assertEqual(self.food.name, "Roti gandum")
        self.assertEqual(FoodItem.objects.count(), 2)

    def test_public_drive_links_and_direct_photo_urls_can_be_saved(self):
        for url in ("https://drive.google.com/file/d/photo-123/view?usp=sharing", "https://example.com/photo?id=123&signature=abc", ""):
            with self.subTest(url=url):
                response = self.client.post(reverse("FoodItem:change_food_item", args=[self.food.pk]), self.food_data(image_url=url))
                self.assertEqual(response.status_code, 302)
                self.food.refresh_from_db()
                self.assertEqual(self.food.image_url, url)

    def test_other_user_cannot_edit_delete_or_change_status(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse("FoodItem:change_food_item", args=[self.food.pk]), self.food_data(name="forged")).status_code, 403)
        self.assertEqual(self.client.post(reverse("FoodItem:delete_food_item", args=[self.food.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("FoodItem:make_food_item_status_consumed", args=[self.food.pk])).status_code, 403)
        self.food.refresh_from_db()
        self.assertEqual(self.food.name, "Roti gandum")
        self.assertEqual(self.food.status, "STORED")

    def test_malformed_api_filters_return_400(self):
        for filters in ({"id": "not-an-id"}, {"id": "9" * 40}, {"id": "-1"}, {"purchase-date": "2026-99-99"}, {"expiration-date": "no-date"}):
            with self.subTest(filters=filters):
                self.assertEqual(self.client.get(reverse("FoodItem:get_food_items"), filters).status_code, 400)

    def test_public_api_requires_live_available_offer(self):
        post = self.publish()
        FoodItem.objects.create(owner=self.owner, name="Orphan offer", category="OTHER", status="OFFERED", purchase_date=timezone.localdate(), expiration_date=self.food.expiration_date)
        self.client.force_login(self.other)
        response = self.client.get(reverse("FoodItem:get_food_items"), {"view-public": "true"})
        self.assertEqual([item["id"] for item in response.json()], [self.food.pk])
        post.is_active = False
        post.save()
        self.assertEqual(self.client.get(reverse("FoodItem:get_food_items"), {"view-public": "true"}).json(), [])

    def test_consumed_closes_offer_and_removes_pin(self):
        post = self.publish()
        response = self.client.post(reverse("FoodItem:make_food_item_status_consumed", args=[self.food.pk]))
        self.assertEqual(response.status_code, 200)
        post.refresh_from_db()
        self.food.refresh_from_db()
        self.assertFalse(post.is_active)
        self.assertEqual(self.food.status, "CONSUMED")
        self.assertEqual(self.client.get(reverse("Location:map")).context["pins"], [])
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("sharedpost:detail", args=[post.pk])).status_code, 404)

    def test_stored_closes_offer_and_allows_explicit_republication(self):
        old = self.publish()
        response = self.client.post(reverse("FoodItem:change_status", args=[self.food.pk]), {"status": "STORED"})
        self.assertRedirects(response, reverse("FoodItem:list_food_items"))
        old.refresh_from_db()
        self.assertFalse(old.is_active)
        new = self.publish()
        self.assertNotEqual(new.pk, old.pk)
        self.assertEqual(SharedPost.objects.filter(food_item=self.food, is_active=True).count(), 1)

    def test_direct_offered_api_cannot_publish_without_pickup(self):
        response = self.client.post(reverse("FoodItem:make_food_item_status_offered", args=[self.food.pk]))
        self.assertEqual(response.status_code, 409)
        self.assertIn(reverse("sharedpost:create"), response.json()["create_url"])
        self.food.refresh_from_db()
        self.assertEqual(self.food.status, "STORED")

    def test_expiry_edit_closes_offer_and_future_edit_does_not_reopen_it(self):
        post = self.publish()
        url = reverse("FoodItem:change_food_item", args=[self.food.pk])
        response = self.client.post(url, self.food_data(expiration_date=str(timezone.localdate() - timedelta(days=1))))
        self.assertEqual(response.status_code, 302)
        post.refresh_from_db()
        self.food.refresh_from_db()
        self.assertFalse(post.is_active)
        self.assertEqual(self.food.status, "STORED")
        self.client.post(url, self.food_data(expiration_date=str(timezone.localdate() + timedelta(days=5))))
        post.refresh_from_db()
        self.assertFalse(post.is_active)

    def test_status_failure_rolls_back_offer_deactivation(self):
        post = self.publish()
        with patch.object(FoodItem, "save", side_effect=RuntimeError("save failed")):
            with self.assertRaises(RuntimeError):
                self.client.post(reverse("FoodItem:make_food_item_status_consumed", args=[self.food.pk]))
        post.refresh_from_db()
        self.food.refresh_from_db()
        self.assertTrue(post.is_active)
        self.assertEqual(self.food.status, "OFFERED")

    def test_correcting_naturally_expired_food_requires_republication(self):
        post = self.publish()
        FoodItem.objects.filter(pk=self.food.pk).update(expiration_date=timezone.localdate() - timedelta(days=1))
        response = self.client.post(reverse("FoodItem:change_food_item", args=[self.food.pk]), self.food_data())
        self.assertEqual(response.status_code, 302)
        post.refresh_from_db()
        self.food.refresh_from_db()
        self.assertFalse(post.is_active)
        self.assertEqual(self.food.status, "STORED")

    def test_delete_food_removes_post_and_keeps_notification_history(self):
        post = self.publish()
        notification = Notification.objects.create(recipient=self.owner, food_item=self.food, title="Pengingat", message="Makananmu")
        response = self.client.post(reverse("FoodItem:delete_food_page", args=[self.food.pk]))
        self.assertRedirects(response, reverse("FoodItem:list_food_items"))
        self.assertFalse(SharedPost.objects.filter(pk=post.pk).exists())
        notification.refresh_from_db()
        self.assertIsNone(notification.food_item_id)
        self.assertTrue(Location.objects.filter(pk=self.location.pk).exists())

    def test_mutations_require_post_and_csrf(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.owner)
        for name in ("delete_food_item", "make_food_item_status_stored", "make_food_item_status_consumed", "make_food_item_status_offered", "change_status"):
            url = reverse("FoodItem:" + name, args=[self.food.pk])
            with self.subTest(name=name):
                self.assertEqual(self.client.get(url).status_code, 405)
                self.assertEqual(csrf_client.post(url).status_code, 403)
        self.assertTrue(FoodItem.objects.filter(pk=self.food.pk).exists())

    def test_default_location_changes_do_not_move_existing_offer(self):
        post = self.publish()
        campus = Location.objects.create(owner=self.owner, area_name="Kampus", latitude="-6.350000", longitude="106.820000")
        self.client.post(reverse("Location:set_default", args=[campus.pk]))
        post.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(post.location_id, self.location.pk)
        self.assertEqual(self.profile.default_location_id, campus.pk)

    def test_share_form_preselects_only_eligible_owned_food_and_no_location(self):
        response = self.client.get(reverse("sharedpost:create"), {"food": self.food.pk})
        self.assertEqual(response.context["form"].initial["food_item"], self.food.pk)
        self.assertNotIn("location", response.context["form"].initial)
        for value in (self.other_food.pk, "invalid", "²", "9" * 99):
            response = self.client.get(reverse("sharedpost:create"), {"food": value})
            self.assertNotIn("food_item", response.context["form"].initial)

    def test_available_post_links_to_donor_contact_without_disclosing_email(self):
        post = self.publish()
        self.client.force_login(self.other)
        response = self.client.get(reverse("sharedpost:detail", args=[post.pk]))
        self.assertContains(response, reverse("userprofile:donor_contact", args=[self.owner.pk]))
        self.assertNotContains(response, self.owner.email)
        response = self.client.get(reverse("userprofile:donor_contact", args=[self.owner.pk]))
        self.assertNotContains(response, self.owner.email)
        self.assertNotContains(response, str(self.location.latitude))


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class FoodReminderHookTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="reminder_owner", email="owner@example.com")
        self.other = get_user_model().objects.create_user(username="reminder_other", email="other@example.com")
        self.food = self.make_food(self.owner, "Roti lama")
        self.other_food = self.make_food(self.other, "Makanan pengguna lain")
        self.client.force_login(self.owner)

    def make_food(self, owner, name):
        return FoodItem.objects.create(
            owner=owner, name=name, status="STORED", category="GRAIN",
            purchase_date=timezone.localdate(), expiration_date=timezone.localdate() + timedelta(days=3),
        )

    def data(self, name):
        return {
            "name": name, "category": "GRAIN", "purchase_date": str(timezone.localdate()),
            "expiration_date": str(timezone.localdate() + timedelta(days=3)), "image_url": "",
        }

    def test_add_sends_only_new_food_reminder_after_commit(self):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            response = self.client.post(reverse("FoodItem:add_food_item"), self.data("Roti baru"))
            self.assertEqual(response.status_code, 302)
            self.assertFalse(Notification.objects.exists())
        self.assertEqual(len(callbacks), 1)
        new_food = FoodItem.objects.get(name="Roti baru")
        reminder = Notification.objects.get()
        self.assertEqual(reminder.food_item, new_food)
        self.assertEqual(reminder.recipient, self.owner)
        self.assertEqual(reminder.email_status, Notification.EmailStatus.SENT)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.owner.email])

    def test_edit_scopes_dispatch_and_reads_latest_email(self):
        unrelated = Notification.objects.create(
            recipient=self.other, food_item=self.other_food, title="Other pending", message="Other food",
            reminder_days=3, expiry_date=self.other_food.expiration_date,
            email_status=Notification.EmailStatus.PENDING,
        )
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("FoodItem:change_food_item", args=[self.food.pk]), self.data("Roti diperbarui"))
            self.assertEqual(response.status_code, 302)
            get_user_model().objects.filter(pk=self.owner.pk).update(email="new-address@example.com")
        self.food.refresh_from_db()
        unrelated.refresh_from_db()
        self.assertEqual(self.food.name, "Roti diperbarui")
        self.assertEqual(unrelated.email_status, Notification.EmailStatus.PENDING)
        self.assertEqual(Notification.objects.filter(food_item=self.food).count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["new-address@example.com"])

    def test_notification_failure_does_not_lose_added_food(self):
        with patch("FoodItem.views.generate_food_reminders", side_effect=RuntimeError("reminder unavailable")):
            with self.assertLogs(level="ERROR"):
                with self.captureOnCommitCallbacks(execute=True):
                    response = self.client.post(reverse("FoodItem:add_food_item"), self.data("Makanan tetap tersimpan"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(FoodItem.objects.filter(name="Makanan tetap tersimpan", owner=self.owner).exists())

    def test_dispatch_failure_keeps_food_edit_and_pending_notification(self):
        with patch("FoodItem.views.send_pending_reminder_emails", side_effect=RuntimeError("mail service unavailable")):
            with self.assertLogs(level="ERROR"):
                with self.captureOnCommitCallbacks(execute=True):
                    response = self.client.post(reverse("FoodItem:change_food_item", args=[self.food.pk]), self.data("Edit tetap tersimpan"))
        self.assertEqual(response.status_code, 302)
        self.food.refresh_from_db()
        self.assertEqual(self.food.name, "Edit tetap tersimpan")
        self.assertEqual(Notification.objects.get(food_item=self.food).email_status, Notification.EmailStatus.PENDING)

    def test_failed_save_never_registers_delivery_callback(self):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            with patch.object(FoodItem, "save", side_effect=RuntimeError("database unavailable")):
                with self.assertRaises(RuntimeError):
                    self.client.post(reverse("FoodItem:add_food_item"), self.data("Tidak tersimpan"))
        self.assertEqual(callbacks, [])
        self.assertFalse(FoodItem.objects.filter(name="Tidak tersimpan").exists())
        self.assertFalse(Notification.objects.exists())
