"""Exercise GPS and manual fallback without requesting the developer's real location."""
import os
from contextlib import contextmanager
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client
from django.urls import reverse
from playwright.sync_api import expect, sync_playwright

from userprofile.models import UserProfile
from .models import Location


class SavedLocationBrowserTests(StaticLiveServerTestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="browser_location_owner")
        UserProfile.objects.create(user=self.owner)

    @contextmanager
    def open_manager(self, gps_error=None, mobile=False):
        client = Client()
        client.force_login(self.owner)
        with sync_playwright() as playwright:
            options = {"headless": os.getenv("BROWSER_HEADLESS", "1") != "0"}
            channel = os.getenv("BROWSER_CHANNEL", "chromium")
            if channel != "chromium":
                options["channel"] = channel
            browser = playwright.chromium.launch(**options)
            try:
                context = browser.new_context(
                    viewport={"width": 390, "height": 844} if mobile else {"width": 1440, "height": 1000},
                    geolocation={"latitude": -6.36123456, "longitude": 106.82123456, "accuracy": 30},
                    permissions=["geolocation"],
                    reduced_motion="reduce",
                )
                if gps_error is not None:
                    context.add_init_script(
                        "Object.defineProperty(navigator, 'geolocation', {value: {"
                        "getCurrentPosition: function (success, failure) {failure({code: "
                        + str(gps_error) + "});}}});"
                    )
                context.add_cookies([{
                    "name": settings.SESSION_COOKIE_NAME,
                    "value": client.cookies[settings.SESSION_COOKIE_NAME].value,
                    "url": self.live_server_url,
                }])
                page = context.new_page()
                page.goto(self.live_server_url + reverse("Location:manage"))
                yield page
            finally:
                browser.close()

    def test_gps_fills_six_decimal_coordinates_but_only_save_persists(self):
        with self.open_manager(mobile=True) as page:
            expect(page.get_by_label("Lintang (latitude)")).to_have_value("")
            expect(page.get_by_label("Bujur (longitude)")).to_have_value("")
            self.assertEqual(page.request.get(self.live_server_url + reverse("Location:get_locations")).json(), [])
            page.get_by_role("button", name="Gunakan lokasi saat ini (GPS)").click()
            expect(page.get_by_label("Lintang (latitude)")).to_have_value("-6.361235")
            expect(page.get_by_label("Bujur (longitude)")).to_have_value("106.821235")
            expect(page.locator("#location-gps-status")).to_contain_text("Periksa dan beri nama")
            self.assertEqual(page.request.get(self.live_server_url + reverse("Location:get_locations")).json(), [])
            page.get_by_label("Nama lokasi / area").fill("Rumah — Kukusan")
            page.get_by_label("Jadikan lokasi bawaan untuk membuka peta").check()
            page.get_by_role("button", name="Simpan lokasi").click()
            expect(page.get_by_role("heading", name="Rumah — Kukusan")).to_be_visible()
        location = Location.objects.get(owner=self.owner)
        self.assertEqual(location.latitude, Decimal("-6.361235"))
        self.assertEqual(UserProfile.objects.get(user=self.owner).default_location, location)

    def test_denied_gps_leaves_form_available_for_manual_entry(self):
        with self.open_manager(gps_error=1) as page:
            page.get_by_role("button", name="Gunakan lokasi saat ini (GPS)").click()
            expect(page.locator("#location-gps-status")).to_contain_text("Izin lokasi ditolak")
            expect(page.get_by_label("Lintang (latitude)")).to_have_value("")
            self.assertEqual(page.request.get(self.live_server_url + reverse("Location:get_locations")).json(), [])
            page.get_by_label("Nama lokasi / area").fill("Kampus")
            page.get_by_label("Lintang (latitude)").fill("-6.360000")
            page.get_by_label("Bujur (longitude)").fill("106.820000")
            page.get_by_role("button", name="Simpan lokasi").click()
            expect(page.get_by_role("heading", name="Kampus")).to_be_visible()
        self.assertEqual(Location.objects.get(owner=self.owner).area_name, "Kampus")

    def test_gps_timeout_preserves_manually_entered_point(self):
        with self.open_manager(gps_error=3) as page:
            page.get_by_label("Lintang (latitude)").fill("-6.360000")
            page.get_by_label("Bujur (longitude)").fill("106.820000")
            page.get_by_role("button", name="Gunakan lokasi saat ini (GPS)").click()
            expect(page.locator("#location-gps-status")).to_contain_text("melewati batas waktu")
            expect(page.get_by_label("Lintang (latitude)")).to_have_value("-6.360000")
            expect(page.get_by_role("button", name="Gunakan lokasi saat ini (GPS)")).to_be_enabled()
        self.assertFalse(Location.objects.exists())

    def test_search_requires_explicit_result_selection_and_save(self):
        with self.open_manager() as page:
            page.route("**/location/search/**", lambda route: route.fulfill(json=[{
                "area_name": "Kukusan", "display_name": "Kukusan, Depok",
                "latitude": "-6.361235", "longitude": "106.821235",
            }]))
            page.get_by_label("Atau cari nama tempat / area").fill("Kukusan")
            page.get_by_role("button", name="Cari", exact=True).click()
            expect(page.get_by_role("button", name="Kukusan, Depok", exact=True)).to_be_visible()
            expect(page.get_by_label("Lintang (latitude)")).to_have_value("")
            page.get_by_role("button", name="Kukusan, Depok", exact=True).click()
            expect(page.get_by_label("Nama lokasi / area")).to_have_value("Kukusan")
            expect(page.get_by_label("Lintang (latitude)")).to_have_value("-6.361235")
        self.assertFalse(Location.objects.exists())
