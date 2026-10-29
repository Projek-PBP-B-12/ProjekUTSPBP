from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from FoodItem.models import FoodItem
from Location.models import Location

from .models import SharedPost


class OfferMapLinkTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username="map_link_owner")
        cls.visitor = get_user_model().objects.create_user(username="map_link_visitor")
        cls.location = Location.objects.create(
            owner=cls.owner, area_name="Beji", latitude="-6.371234", longitude="106.831234",
        )
        cls.food = FoodItem.objects.create(
            owner=cls.owner, name="Soto", status="OFFERED",
            purchase_date=timezone.localdate(), expiration_date=timezone.localdate() + timedelta(days=3),
        )
        cls.post = SharedPost.objects.create(food_item=cls.food, location=cls.location, description="Ambil di lobi kos sore hari.")

    def setUp(self):
        self.client.force_login(self.visitor)

    def test_available_detail_links_to_its_offer_on_the_map(self):
        response = self.client.get(reverse("sharedpost:detail", args=[self.post.pk]))
        target = reverse("Location:map") + f"?post={self.post.pk}"
        self.assertEqual(response.context["map_url"], target)
        self.assertContains(response, f'href="{target}"')
        self.assertContains(response, "Lokasi umum")
        self.assertContains(response, "Hubungi donor")

    def test_map_selects_available_offer_without_exposing_exact_coordinates(self):
        response = self.client.get(reverse("Location:map"), {"post": self.post.pk})
        self.assertEqual(response.context["selected_post_id"], self.post.pk)
        self.assertFalse(response.context["selection_unavailable"])
        self.assertEqual(response.context["pins"][0]["latitude"], "-6.371")
        self.assertEqual(response.context["pins"][0]["longitude"], "106.831")
        self.assertNotContains(response, "-6.371234")
        self.assertNotContains(response, "106.831234")
        self.assertContains(response, 'class="map-selected-offer"')

    def test_unavailable_owner_detail_has_no_map_button(self):
        self.client.force_login(self.owner)
        for active, status, days in [(False, "CONSUMED", 3), (True, "STORED", 3), (True, "OFFERED", -1)]:
            with self.subTest(active=active, status=status, days=days):
                SharedPost.objects.filter(pk=self.post.pk).update(is_active=active)
                FoodItem.objects.filter(pk=self.food.pk).update(status=status, expiration_date=timezone.localdate() + timedelta(days=days))
                response = self.client.get(reverse("sharedpost:detail", args=[self.post.pk]))
                self.assertIsNone(response.context["map_url"])
                self.assertNotContains(response, "Lihat lokasi")

    def test_stale_or_invalid_selection_keeps_map_available(self):
        SharedPost.objects.filter(pk=self.post.pk).update(is_active=False)
        for value in [str(self.post.pk), "999999", "0", "abc", "9" * 100, '<script>alert(1)</script>']:
            with self.subTest(post=value):
                response = self.client.get(reverse("Location:map"), {"post": value})
                self.assertEqual(response.status_code, 200)
                self.assertIsNone(response.context["selected_post_id"])
                self.assertTrue(response.context["selection_unavailable"])
                self.assertNotContains(response, "Soto")
                self.assertNotContains(response, "<script>alert(1)</script>")
        response = self.client.get(reverse("Location:map"))
        self.assertFalse(response.context["selection_unavailable"])

    def test_foreign_pickup_location_does_not_link_to_a_hidden_pin(self):
        foreign = Location.objects.create(owner=self.visitor, area_name="Lokasi lain", latitude=0, longitude=0)
        SharedPost.objects.filter(pk=self.post.pk).update(location=foreign)
        detail = self.client.get(reverse("sharedpost:detail", args=[self.post.pk]))
        self.assertIsNone(detail.context["map_url"])
        for headers in [{}, {"HTTP_HX_REQUEST": "true"}]:
            board = self.client.get(reverse("sharedpost:list"), **headers)
            self.assertNotContains(board, f'href="{reverse("Location:map")}?post={self.post.pk}"')
        response = self.client.get(reverse("Location:map"), {"post": self.post.pk})
        self.assertIsNone(response.context["selected_post_id"])
        self.assertEqual(response.context["pins"], [])
