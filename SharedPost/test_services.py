from datetime import timedelta
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from FoodItem.models import FoodItem
from Location.models import Location
from Location.services import distance_km
from .models import SharedPost
from .services import get_map_pins, normalize_photo_url


class PhotoURLTests(SimpleTestCase):
    def test_drive_links_are_normalized(self):
        for url in [
            "https://drive.google.com/file/d/abc_123-XYZ/view?usp=sharing",
            "https://drive.google.com/open?id=abc_123-XYZ",
            "https://drive.google.com/uc?export=view&id=abc_123-XYZ",
            "https://drive.google.com/uc?id=abc_123-XYZ&export=view",
        ]:
            with self.subTest(url=url):
                self.assertEqual(
                    normalize_photo_url(url),
                    "https://drive.google.com/thumbnail?id=abc_123-XYZ&sz=w1000",
                )

    def test_empty_and_other_urls(self):
        self.assertIsNone(normalize_photo_url(None))
        self.assertIsNone(normalize_photo_url(""))
        for url in [
            "https://example.com/roti.jpg",
            "https://drive.google.com/thumbnail?id=abc&sz=w1200",
            "https://drive.google.com/open",
            "https://notdrive.google.com/file/d/abc/view",
            "https://example.com/?url=drive.google.com/file/d/abc/view",
            "https://drive.google.com/uc?id=abc%2Fdef",
            "https://[invalid",
        ]:
            with self.subTest(url=url):
                self.assertEqual(normalize_photo_url(url), url)


class MapPinTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        owner = get_user_model().objects.create_user(username="map_donor")
        cls.location = Location.objects.create(
            owner=owner, area_name="Beji",
            latitude="-6.360000", longitude="106.830000",
        )
        cls.food = FoodItem.objects.create(
            owner=owner, name="Roti gandum", category="GRAIN", status="OFFERED",
            purchase_date=timezone.localdate(),
            expiration_date=timezone.localdate() + timedelta(days=3),
            image_url="https://drive.google.com/file/d/abc/view",
        )
        cls.post = SharedPost.objects.create(
            food_item=cls.food, location=cls.location,
            description="Ambil di lobi kos sore hari.",
        )

    def test_pin_data_without_origin(self):
        with self.assertNumQueries(1):
            pins = get_map_pins(SharedPost.objects.filter(pk=self.post.pk))
        self.assertEqual(pins, [{
            "id": self.post.pk,
            "title": "Roti gandum",
            "category": "Grain",
            "description": "Ambil di lobi kos sore hari.",
            "photo_url": "https://drive.google.com/thumbnail?id=abc&sz=w1000",
            "area_name": "Beji",
            "latitude": "-6.360",
            "longitude": "106.830",
            "distance_km": None,
            "detail_url": reverse("sharedpost:detail", args=[self.post.pk]),
        }])

    def test_distance_with_origin(self):
        for lat, lon in [(self.location.latitude, self.location.longitude), (-6.37, 106.82), (0, 0)]:
            with self.subTest(latitude=lat, longitude=lon):
                pins = get_map_pins(
                    SharedPost.objects.all(),
                    SimpleNamespace(latitude=lat, longitude=lon),
                )
                self.assertEqual(pins[0]["distance_km"], round(distance_km(
                    lat, lon, self.location.latitude, self.location.longitude,
                ), 2))

    def test_empty_queryset_and_missing_photo(self):
        self.assertEqual(get_map_pins(SharedPost.objects.none()), [])
        self.food.image_url = ""
        self.food.save(update_fields=["image_url"])
        self.assertIsNone(get_map_pins(SharedPost.objects.all())[0]["photo_url"])

    def test_public_distance_uses_the_approximate_pin_instead_of_exact_home(self):
        self.location.latitude = "-6.371234"
        self.location.longitude = "106.831234"
        self.location.save(update_fields=["latitude", "longitude"])
        pins = get_map_pins(SharedPost.objects.all(), origin=self.location)
        self.assertEqual(pins[0]["latitude"], "-6.371")
        self.assertEqual(pins[0]["longitude"], "106.831")
        expected = round(distance_km(-6.371234, 106.831234, -6.371, 106.831), 2)
        self.assertGreater(expected, 0)
        self.assertEqual(pins[0]["distance_km"], expected)


class DistanceTests(SimpleTestCase):
    def test_same_and_opposite_points_remain_finite(self):
        self.assertEqual(distance_km(0, 0, 0, 0), 0)
        self.assertAlmostEqual(distance_km(90, 0, -90, 180), 20015.114442, places=5)
