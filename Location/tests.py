from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import requests
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from FoodItem.models import FoodItem
from SharedPost.models import SharedPost
from userprofile.models import UserProfile
from .models import Location
from .services import GeocodingError, distance_km, geocode_address


class SavedLocationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username="location-owner")
        cls.other = get_user_model().objects.create_user(username="location-other")
        cls.home = Location.objects.create(owner=cls.owner, area_name="Rumah — Kukusan", latitude="-6.361234", longitude="106.821234")
        cls.campus = Location.objects.create(owner=cls.owner, area_name="Kampus", latitude="-6.362345", longitude="106.822345")
        cls.private = Location.objects.create(owner=cls.other, area_name="Alamat pribadi lain", latitude="-6.371234", longitude="106.831234")
        cls.profile = UserProfile.objects.create(user=cls.owner, default_location=cls.home)

    def setUp(self):
        self.client.force_login(self.owner)

    def data(self, **changes):
        return {"area_name": "Kos — Beji", "latitude": "-6.350000", "longitude": "106.840000", **changes}

    def offer(self, location=None, status="OFFERED", active=True, days=3, owner=None):
        location = location or self.home
        food = FoodItem.objects.create(
            owner=owner or location.owner, name="Roti " + str(FoodItem.objects.count()),
            purchase_date=timezone.localdate() - timedelta(days=10),
            expiration_date=timezone.localdate() + timedelta(days=days), status=status,
        )
        return SharedPost.objects.create(food_item=food, location=location, description="Ambil di depan gerbang.", is_active=active)

    def test_guest_cannot_access_private_locations(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("Location:get_locations")).status_code, 401)
        self.assertEqual(self.client.post(reverse("Location:create_location"), self.data()).status_code, 401)
        for name in ["manage", "map"]:
            with self.subTest(page=name):
                response = self.client.get(reverse("Location:" + name))
                self.assertRedirects(response, reverse("userprofile:login") + "?next=" + reverse("Location:" + name))

    def test_list_only_contains_owned_locations_and_is_not_cached(self):
        response = self.client.get(reverse("Location:get_locations"))
        self.assertEqual({item["id"] for item in response.json()}, {self.home.pk, self.campus.pk})
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(self.client.get(reverse("Location:get_locations"), {"id": self.private.pk}).json(), [])
        for invalid in ["invalid", "²", "9" * 50, str(2**63)]:
            self.assertEqual(self.client.get(reverse("Location:get_locations"), {"id": invalid}).status_code, 400)

    def test_create_many_locations_ignores_forged_owner(self):
        response = self.client.post(reverse("Location:create_location"), self.data(owner=self.other.pk))
        self.assertEqual(response.status_code, 201)
        created = Location.objects.get(pk=response.json()["id"])
        self.assertEqual(created.owner, self.owner)
        self.assertEqual(self.owner.locations.count(), 3)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.default_location, self.home)

    def test_creation_can_explicitly_choose_new_default(self):
        response = self.client.post(reverse("Location:manage"), self.data(make_default="on"))
        self.assertRedirects(response, reverse("Location:manage"))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.default_location.area_name, "Kos — Beji")
        self.assertEqual(self.owner.locations.count(), 3)

    def test_zero_coordinates_are_valid(self):
        response = self.client.post(reverse("Location:create_location"), self.data(latitude="0", longitude="0", make_default="on"))
        self.assertEqual(response.status_code, 201)
        center = self.client.get(reverse("Location:map")).context["map_center"]
        self.assertEqual(Decimal(center["latitude"]), Decimal(0))
        self.assertTrue(center["is_default"])

    def test_invalid_coordinates_do_not_create_locations(self):
        for invalid in [{"latitude": "91"}, {"longitude": "-181"}, {"latitude": ""}, {"longitude": "NaN"}, {"latitude": "1.1234567"}]:
            with self.subTest(invalid=invalid):
                response = self.client.post(reverse("Location:create_location"), self.data(**invalid))
                self.assertEqual(response.status_code, 400)
        self.assertEqual(self.owner.locations.count(), 2)

    def test_database_rejects_out_of_range_coordinates(self):
        for field, value in [("latitude", 91), ("longitude", -181)]:
            with self.subTest(field=field), self.assertRaises(IntegrityError), transaction.atomic():
                Location.objects.filter(pk=self.home.pk).update(**{field: value})

    def test_user_cannot_read_edit_delete_or_choose_anothers_location(self):
        for name, method in [("manage_edit", "get"), ("manage_edit", "post"), ("manage_delete", "post"), ("set_default", "post"), ("update_location", "post"), ("delete_location", "post")]:
            with self.subTest(endpoint=name, method=method):
                response = getattr(self.client, method)(reverse("Location:" + name, args=[self.private.pk]), self.data())
                self.assertEqual(response.status_code, 404)
        self.assertTrue(Location.objects.filter(pk=self.private.pk).exists())

    def test_mutations_require_post_and_csrf(self):
        for name in ["update_location", "delete_location", "manage_delete", "set_default"]:
            with self.subTest(endpoint=name):
                self.assertEqual(self.client.get(reverse("Location:" + name, args=[self.home.pk])).status_code, 405)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.owner)
        for name, args in [("create_location", []), ("manage", []), ("set_default", [self.home.pk]), ("manage_delete", [self.home.pk])]:
            with self.subTest(csrf=name):
                self.assertEqual(csrf_client.post(reverse("Location:" + name, args=args), self.data()).status_code, 403)

    def test_edit_owned_unused_location(self):
        response = self.client.post(reverse("Location:manage_edit", args=[self.home.pk]), self.data())
        self.assertRedirects(response, reverse("Location:manage"))
        self.home.refresh_from_db()
        self.assertEqual(self.home.area_name, "Kos — Beji")
        self.assertEqual(self.home.owner, self.owner)

    def test_existing_offer_freezes_location_name_and_point(self):
        post = self.offer()
        response = self.client.post(reverse("Location:update_location", args=[self.home.pk]), self.data())
        self.assertEqual(response.status_code, 409)
        response = self.client.post(reverse("Location:manage_edit", args=[self.home.pk]), self.data())
        self.assertContains(response, "tidak dapat diubah")
        self.home.refresh_from_db()
        post.refresh_from_db()
        self.assertEqual(self.home.latitude, Decimal("-6.361234"))
        self.assertEqual(self.home.area_name, "Rumah — Kukusan")
        self.assertEqual(post.location_id, self.home.pk)

    def test_deleting_location_used_by_offer_is_blocked(self):
        post = self.offer()
        response = self.client.post(reverse("Location:delete_location", args=[self.home.pk]))
        self.assertEqual(response.status_code, 409)
        response = self.client.post(reverse("Location:manage_delete", args=[self.home.pk]), follow=True)
        self.assertContains(response, "Lokasi masih dipakai")
        self.assertTrue(SharedPost.objects.filter(pk=post.pk).exists())
        self.assertTrue(Location.objects.filter(pk=self.home.pk).exists())

    def test_default_changes_do_not_move_existing_offers(self):
        post = self.offer()
        self.assertRedirects(self.client.post(reverse("Location:set_default", args=[self.campus.pk])), reverse("Location:manage"))
        self.profile.refresh_from_db()
        post.refresh_from_db()
        self.assertEqual(self.profile.default_location, self.campus)
        self.assertEqual(post.location, self.home)

    def test_deleting_unused_default_clears_pointer_without_deleting_profile(self):
        response = self.client.post(reverse("Location:delete_location", args=[self.home.pk]))
        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertIsNone(self.profile.default_location)
        center = self.client.get(reverse("Location:map")).context["map_center"]
        self.assertFalse(center["is_default"])

    def test_default_choice_creates_missing_profile(self):
        self.profile.delete()
        self.client.post(reverse("Location:set_default", args=[self.campus.pk]))
        self.assertEqual(UserProfile.objects.get(user=self.owner).default_location, self.campus)

    def test_management_page_hides_other_users_locations(self):
        response = self.client.get(reverse("Location:manage"))
        self.assertContains(response, self.home.area_name)
        self.assertNotContains(response, self.private.area_name)
        self.assertNotContains(response, str(self.private.latitude))
        self.assertContains(response, "use-current-location")
        self.assertIn("no-store", response["Cache-Control"])

    def test_map_uses_saved_default_and_does_not_include_private_unsold_locations(self):
        response = self.client.get(reverse("Location:map"))
        self.assertEqual(response.context["map_center"]["latitude"], "-6.361234")
        self.assertEqual(response.context["pins"], [])
        self.assertNotContains(response, self.private.area_name)
        self.assertNotContains(response, "-6.371234")
        self.assertIn("no-store", response["Cache-Control"])

    def test_map_only_includes_available_offers_with_approximate_coordinates(self):
        public = self.offer(self.private)
        self.offer(status="STORED")
        self.offer(status="CONSUMED")
        self.offer(active=False)
        self.offer(days=-1)
        self.offer(self.home, owner=self.other)  # Legacy inconsistent owner relation.
        pins = self.client.get(reverse("Location:map")).context["pins"]
        self.assertEqual([pin["id"] for pin in pins], [public.pk])
        self.assertEqual(pins[0]["latitude"], "-6.371")
        self.assertEqual(pins[0]["longitude"], "106.831")
        self.assertEqual(pins[0]["detail_url"], reverse("sharedpost:detail", args=[public.pk]))
        response = self.client.get(reverse("Location:map"))
        self.assertNotContains(response, "-6.371234")
        self.assertNotContains(response, "106.831234")

    def test_map_excludes_inactive_donor(self):
        self.offer(self.private)
        self.other.is_active = False
        self.other.save(update_fields=["is_active"])
        self.assertEqual(self.client.get(reverse("Location:map")).context["pins"], [])

    def test_map_keeps_latest_photo_and_distance_services_with_saved_default(self):
        post = self.offer(self.private)
        food = post.food_item
        food.image_url = "https://drive.google.com/file/d/food-photo-123/view"
        food.save(update_fields=["image_url"])
        response = self.client.get(reverse("Location:map"))
        pin = response.context["pins"][0]
        self.assertEqual(pin["photo_url"], "https://drive.google.com/thumbnail?id=food-photo-123&sz=w1000")
        self.assertEqual(pin["area_name"], self.private.area_name)
        self.assertEqual(pin["description"], post.description)
        self.assertEqual(pin["distance_km"], round(distance_km(
            self.home.latitude, self.home.longitude, "-6.371", "106.831",
        ), 2))
        self.client.post(reverse("Location:set_default", args=[self.campus.pk]))
        pin_after = self.client.get(reverse("Location:map")).context["pins"][0]
        self.assertEqual(pin_after["latitude"], pin["latitude"])
        self.assertEqual(pin_after["longitude"], pin["longitude"])
        self.assertEqual(pin_after["distance_km"], round(distance_km(
            self.campus.latitude, self.campus.longitude, "-6.371", "106.831",
        ), 2))

    @patch("Location.views.geocode_address")
    def test_search_validates_input_and_handles_upstream_failure(self, geocode):
        self.assertEqual(self.client.get(reverse("Location:search_locations"), {"q": " a "}).status_code, 400)
        geocode.assert_not_called()
        geocode.side_effect = GeocodingError("Layanan sedang tidak tersedia.")
        response = self.client.get(reverse("Location:search_locations"), {"q": "Depok"})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["message"], "Layanan sedang tidak tersedia.")


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "location-service-tests"}})
class GeocodingTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @patch("Location.services.requests.get")
    def test_search_formats_coordinates_and_caches_repeated_queries(self, get):
        get.return_value.json.return_value = [{"lat": "-6.36123456", "lon": "106.82123456", "display_name": "Kukusan, Depok", "address": {"suburb": "Kukusan"}}]
        result = geocode_address("  Kukusan  Depok ")
        self.assertEqual(result[0]["latitude"], "-6.361235")
        self.assertEqual(result[0]["area_name"], "Kukusan")
        self.assertEqual(geocode_address("kukusan depok"), result)
        get.assert_called_once()

    @patch("Location.services.requests.get")
    def test_search_requests_are_rate_limited(self, get):
        get.return_value.json.return_value = []
        geocode_address("Depok")
        with self.assertRaisesMessage(GeocodingError, "Tunggu sebentar"):
            geocode_address("Jakarta")
        get.assert_called_once()

    @patch("Location.services.requests.get", side_effect=requests.Timeout)
    def test_timeout_becomes_friendly_error(self, get):
        with self.assertRaisesMessage(GeocodingError, "sedang tidak tersedia"):
            geocode_address("Depok")

    @patch("Location.services.requests.get")
    def test_malformed_or_invalid_coordinates_do_not_escape_as_server_errors(self, get):
        for result in [None, [{"lat": "NaN", "lon": "106.8", "display_name": "Area"}], [{"lat": "91", "lon": "106.8", "display_name": "Area"}], [{"name": "No coordinates"}]]:
            with self.subTest(result=result):
                cache.clear()
                get.return_value.json.return_value = result
                with self.assertRaisesMessage(GeocodingError, "tidak valid"):
                    geocode_address("Depok")
