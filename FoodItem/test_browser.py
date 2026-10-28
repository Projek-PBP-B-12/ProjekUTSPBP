import os
from contextlib import contextmanager
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from playwright.sync_api import expect, sync_playwright

from Location.models import Location
from SharedPost.models import SharedPost
from .models import FoodItem


class InventoryBrowserTests(StaticLiveServerTestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="inventory_browser")
        self.location = Location.objects.create(owner=self.owner, area_name="Rumah", latitude="-6.36", longitude="106.83")
        self.food = FoodItem.objects.create(
            owner=self.owner, name="Roti contoh", category="GRAIN", status="STORED",
            purchase_date=timezone.localdate(), expiration_date=timezone.localdate() + timedelta(days=3),
        )
        FoodItem.objects.create(
            owner=self.owner, name="Apel contoh", category="FRUIT", status="STORED",
            purchase_date=timezone.localdate(), expiration_date=timezone.localdate() + timedelta(days=7),
        )

    @contextmanager
    def open_inventory(self, mobile=False):
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
                    reduced_motion="reduce",
                )
                context.add_cookies([{
                    "name": settings.SESSION_COOKIE_NAME,
                    "value": client.cookies[settings.SESSION_COOKIE_NAME].value,
                    "url": self.live_server_url,
                }])
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(self.live_server_url + reverse("FoodItem:makananku"))
                yield page
                self.assertEqual(errors, [])
            finally:
                browser.close()

    def test_mobile_table_modal_search_and_explicit_pickup(self):
        with self.open_inventory(mobile=True) as page:
            expect(page.locator(".food-row")).to_have_count(2)
            self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), 390)
            row = page.locator(".food-row").filter(has_text="Roti contoh")
            detail = row.get_by_role("button", name="Detail →", exact=True)
            detail.click()
            modal = page.get_by_role("dialog", name="Roti contoh")
            expect(modal).to_be_visible()
            expect(modal.locator("#modal-status")).to_have_text("Tersimpan")
            expect(modal.locator("#modal-image-row")).to_be_hidden()
            page.keyboard.press("Escape")
            expect(modal).to_be_hidden()
            expect(detail).to_be_focused()
            page.get_by_label("Cari makanan", exact=True).fill("Roti")
            page.get_by_role("button", name="Tampilkan", exact=True).click()
            expect(page.locator(".food-row")).to_have_count(1)
            page.get_by_role("link", name="Bagikan", exact=True).click()
            expect(page.get_by_label("Makanan yang dibagikan")).to_have_value(str(self.food.pk))
            expect(page.get_by_label("Lokasi pengambilan")).to_have_value("")
        self.assertFalse(SharedPost.objects.exists())

    def test_marking_food_consumed_closes_its_offer(self):
        self.food.status = "OFFERED"
        self.food.save()
        post = SharedPost.objects.create(
            food_item=self.food, location=self.location,
            description="Ambil di depan gerbang sore hari.",
        )
        with self.open_inventory() as page:
            row = page.locator(".food-row").filter(has_text="Roti contoh")
            expect(row.get_by_role("link", name="Lihat penawaran", exact=True)).to_be_visible()
            row.get_by_role("button", name="Tandai habis", exact=True).click()
            row = page.locator(".food-row").filter(has_text="Roti contoh")
            expect(row).to_contain_text("Sudah habis")
            expect(row.get_by_role("link", name="Lihat penawaran", exact=True)).to_have_count(0)
            expect(row.get_by_role("link", name="Bagikan", exact=True)).to_have_count(0)
        self.food.refresh_from_db()
        post.refresh_from_db()
        self.assertEqual(self.food.status, "CONSUMED")
        self.assertFalse(post.is_active)

    def test_modal_status_toggle_and_confirmed_delete_without_reload(self):
        self.food.status = "OFFERED"
        self.food.save()
        post = SharedPost.objects.create(food_item=self.food, location=self.location, description="Ambil sore hari di gerbang.")
        with self.open_inventory() as page:
            page.evaluate("window.inventoryTestMarker = 'unchanged'")
            row = page.locator(".food-row").filter(has_text="Roti contoh")
            row.get_by_role("button", name="Detail →", exact=True).click()
            modal = page.get_by_role("dialog", name="Roti contoh")
            modal.get_by_role("button", name="Tandai habis", exact=True).click()
            expect(modal).to_be_hidden()
            expect(row).to_contain_text("Sudah dikonsumsi")
            self.assertEqual(page.evaluate("window.inventoryTestMarker"), "unchanged")
            row.get_by_role("button", name="Detail →", exact=True).click()
            modal.get_by_role("button", name="Simpan kembali", exact=True).click()
            expect(modal).to_be_hidden()
            expect(row).to_contain_text("Tersimpan")
            expect(row.get_by_role("link", name="Bagikan", exact=True)).to_be_visible()
            page.once("dialog", lambda dialog: dialog.dismiss())
            row.get_by_role("link", name="Hapus", exact=True).click()
            expect(row).to_have_count(1)
            page.once("dialog", lambda dialog: dialog.accept())
            row.get_by_role("link", name="Hapus", exact=True).click()
            expect(row).to_have_count(0)
            expect(page.locator("#food-amount")).to_have_text("1 Makanan")
            self.assertEqual(page.evaluate("window.inventoryTestMarker"), "unchanged")
        self.assertFalse(FoodItem.objects.filter(pk=self.food.pk).exists())
        self.assertFalse(SharedPost.objects.filter(pk=post.pk).exists())

    def test_failed_ajax_status_keeps_modal_and_food_unchanged(self):
        with self.open_inventory() as page:
            page.route("**/fooditem/api/change/*/status/consumed", lambda route: route.fulfill(status=403, json={"message": "Request not permitted."}))
            row = page.locator(".food-row").filter(has_text="Roti contoh")
            row.get_by_role("button", name="Detail →", exact=True).click()
            modal = page.get_by_role("dialog", name="Roti contoh")
            modal.get_by_role("button", name="Tandai habis", exact=True).click()
            expect(modal.locator("#modal-food-error")).to_have_text("Request not permitted.")
            expect(modal).to_be_visible()
            expect(modal.get_by_role("button", name="Tandai habis", exact=True)).to_be_enabled()
        self.food.refresh_from_db()
        self.assertEqual(self.food.status, "STORED")
