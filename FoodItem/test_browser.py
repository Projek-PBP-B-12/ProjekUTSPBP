import os
from pathlib import Path
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
    def open_inventory(self, mobile=False, javascript=True):
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
                    java_script_enabled=javascript,
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
        photo_url = self.live_server_url + "/test-photo"
        self.food.image_url = photo_url
        self.food.save(update_fields=["image_url"])
        with self.open_inventory(mobile=True) as page:
            page.context.route("**/test-photo", lambda route: route.fulfill(content_type="text/plain", body="Foto percobaan"))
            expect(page.locator(".food-row")).to_have_count(2)
            self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), 390)
            row = page.locator(".food-row").filter(has_text="Roti contoh")
            detail = row.get_by_role("button", name="Detail Roti contoh", exact=True)
            detail.click()
            modal = page.get_by_role("dialog", name="Roti contoh")
            expect(modal).to_be_visible()
            expect(modal.locator("#modal-status")).to_have_text("Tersimpan")
            expect(modal.locator("img")).to_have_count(0)
            photo_link = modal.get_by_role("link", name="Buka foto")
            expect(photo_link).to_have_attribute("href", photo_url)
            with page.expect_popup() as opened_photo:
                photo_link.click()
            photo_page = opened_photo.value
            photo_page.wait_for_load_state()
            self.assertEqual(photo_page.url, photo_url)
            expect(modal).to_be_visible()
            photo_page.close()
            page.keyboard.press("Escape")
            expect(modal).to_be_hidden()
            expect(detail).to_be_focused()
            page.get_by_role("button", name="Detail Apel contoh", exact=True).click()
            expect(page.locator("#modal-photo-row")).to_be_hidden()
            self.assertIsNone(page.locator("#modal-photo-link").get_attribute("href"))
            page.keyboard.press("Escape")
            page.get_by_role("button", name="Cari dan filter makanan", exact=True).click()
            page.get_by_label("Cari makanan", exact=True).fill("Roti")
            page.get_by_role("button", name="Tampilkan", exact=True).click()
            expect(page.locator(".food-row")).to_have_count(1)
            page.get_by_role("button", name="Detail Roti contoh", exact=True).click()
            page.get_by_role("dialog").get_by_role("link", name="Bagikan", exact=True).click()
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
            row.get_by_role("button", name="Detail Roti contoh", exact=True).click()
            modal = page.get_by_role("dialog", name="Roti contoh")
            expect(modal.get_by_role("link", name="Lihat penawaran", exact=True)).to_be_visible()
            modal.get_by_role("button", name="Tandai habis", exact=True).click()
            expect(modal).to_be_hidden()
            row = page.locator(".food-row").filter(has_text="Roti contoh")
            expect(row).to_contain_text("Sudah habis")
            row.get_by_role("button", name="Detail Roti contoh", exact=True).click()
            expect(modal.get_by_role("link", name="Lihat penawaran", exact=True)).to_be_hidden()
            expect(modal.get_by_role("link", name="Bagikan", exact=True)).to_be_hidden()
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
            row.get_by_role("button", name="Detail Roti contoh", exact=True).click()
            modal = page.get_by_role("dialog", name="Roti contoh")
            modal.get_by_role("button", name="Tandai habis", exact=True).click()
            expect(modal).to_be_hidden()
            expect(row).to_contain_text("Sudah dikonsumsi")
            self.assertEqual(page.evaluate("window.inventoryTestMarker"), "unchanged")
            row.get_by_role("button", name="Detail Roti contoh", exact=True).click()
            for width in [1440, 390, 320]:
                page.set_viewport_size({"width": width, "height": 900})
                for name in ["Edit", "Hapus"]:
                    expect(modal.get_by_role("link", name=name, exact=True)).to_be_visible()
                expect(modal.get_by_role("button", name="Simpan kembali", exact=True)).to_be_visible()
                self.assertLessEqual(modal.evaluate("el => el.scrollWidth"), modal.evaluate("el => el.clientWidth"))
                output = os.getenv("BROWSER_SCREENSHOT_DIR")
                if output:
                    Path(output).mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(Path(output) / f"inventory-detail-{width}.png"), full_page=True)
            modal.get_by_role("button", name="Simpan kembali", exact=True).click()
            expect(modal).to_be_hidden()
            expect(row).to_contain_text("Tersimpan")
            row.get_by_role("button", name="Detail Roti contoh", exact=True).click()
            expect(modal.get_by_role("link", name="Bagikan", exact=True)).to_be_visible()
            page.once("dialog", lambda dialog: dialog.dismiss())
            modal.get_by_role("link", name="Hapus", exact=True).click()
            expect(row).to_have_count(1)
            expect(modal).to_be_visible()
            page.once("dialog", lambda dialog: dialog.accept())
            modal.get_by_role("link", name="Hapus", exact=True).click()
            expect(modal).to_be_hidden()
            expect(row).to_have_count(0)
            expect(page.locator("#food-amount")).to_have_text("1 makanan")
            self.assertEqual(page.evaluate("window.inventoryTestMarker"), "unchanged")
        self.assertFalse(FoodItem.objects.filter(pk=self.food.pk).exists())
        self.assertFalse(SharedPost.objects.filter(pk=post.pk).exists())

    def test_failed_ajax_status_keeps_modal_and_food_unchanged(self):
        with self.open_inventory() as page:
            page.route("**/fooditem/api/change/*/status/consumed", lambda route: route.fulfill(status=403, json={"message": "Request not permitted."}))
            row = page.locator(".food-row").filter(has_text="Roti contoh")
            row.get_by_role("button", name="Detail Roti contoh", exact=True).click()
            modal = page.get_by_role("dialog", name="Roti contoh")
            modal.get_by_role("button", name="Tandai habis", exact=True).click()
            expect(modal.locator("#modal-food-error")).to_have_text("Request not permitted.")
            expect(modal).to_be_visible()
            expect(modal.get_by_role("button", name="Tandai habis", exact=True)).to_be_enabled()
        self.food.refresh_from_db()
        self.assertEqual(self.food.status, "STORED")

    def test_figma_layout_and_responsive_inventory_keep_filters_and_actions(self):
        FoodItem.objects.all().delete()
        for name, category, days in [("Bayam segar", "VEGETABLE", 1), ("Susu kedelai", "BEVERAGE", 3), ("Roti gandum", "GRAIN", 5)]:
            FoodItem.objects.create(
                owner=self.owner, name=name, category=category, status="STORED",
                purchase_date=timezone.localdate() - timedelta(days=2),
                expiration_date=timezone.localdate() + timedelta(days=days),
            )
        with self.open_inventory() as page:
            expect(page.get_by_role("heading", name="Inventori pribadi", exact=True)).to_be_visible()
            expect(page.locator("#food-amount")).to_have_text("3 makanan")
            expect(page.locator("#inventory-filters")).to_be_hidden()
            expect(page.locator(".badge-orange")).to_have_count(2)
            expect(page.locator(".badge-green")).to_have_count(1)
            for width in [1440, 1280, 1100, 801, 800, 390, 320]:
                with self.subTest(width=width):
                    page.set_viewport_size({"width": width, "height": 900})
                    expect(page.locator(".food-row")).to_have_count(3)
                    self.assertTrue(page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
                    self.assertTrue(page.locator(".inventory-table-scroll").evaluate("el => el.scrollWidth <= el.clientWidth"))
                    for row in page.locator(".food-row").all():
                        expect(row.locator(".detail-link")).to_be_visible()
                        expect(row.locator(".detail-link")).to_have_text("Detail →")
                    output = os.getenv("BROWSER_SCREENSHOT_DIR")
                    if output and width in [1440, 1280, 390, 320]:
                        Path(output).mkdir(parents=True, exist_ok=True)
                        page.screenshot(path=str(Path(output) / f"inventory-{width}.png"), full_page=True)
            toggle = page.get_by_role("button", name="Cari dan filter makanan", exact=True)
            toggle.click()
            expect(page.get_by_label("Cari makanan", exact=True)).to_be_focused()
            page.get_by_label("Status", exact=True).select_option("CONSUMED")
            page.get_by_role("button", name="Tampilkan", exact=True).click()
            expect(page.locator(".food-row")).to_have_count(0)
            expect(page.locator(".inventory-empty")).to_be_visible()
            expect(page.locator("#inventory-filters")).to_be_visible()
            page.get_by_role("link", name="Reset filter", exact=True).click()
            expect(page.locator(".food-row")).to_have_count(3)
            expect(page.locator("#inventory-filters")).to_be_hidden()

    def test_offered_food_can_be_stored_or_deleted_from_details_with_failure_recovery(self):
        self.food.status = "OFFERED"
        self.food.save()
        post = SharedPost.objects.create(food_item=self.food, location=self.location, description="Ambil sore hari di gerbang.")
        with self.open_inventory() as page:
            row = page.locator(".food-row").filter(has_text="Roti contoh")
            row.get_by_role("button", name="Detail Roti contoh", exact=True).click()
            modal = page.get_by_role("dialog", name="Roti contoh")
            page.route("**/fooditem/api/delete/*", lambda route: route.fulfill(status=500, json={"message": "Gagal menghapus. Coba lagi."}))
            page.once("dialog", lambda dialog: dialog.accept())
            modal.get_by_role("link", name="Hapus", exact=True).click()
            expect(modal.locator("#modal-food-error")).to_have_text("Gagal menghapus. Coba lagi.")
            expect(modal).to_be_visible()
            expect(row).to_have_count(1)
            modal.get_by_role("button", name="Simpan kembali", exact=True).click()
            expect(modal).to_be_hidden()
            row.get_by_role("button", name="Detail Roti contoh", exact=True).click()
            expect(modal.get_by_role("link", name="Bagikan", exact=True)).to_be_visible()
            expect(modal.get_by_role("link", name="Lihat penawaran", exact=True)).to_have_count(0)
        self.food.refresh_from_db()
        post.refresh_from_db()
        self.assertEqual(self.food.status, "STORED")
        self.assertFalse(post.is_active)

    def test_expiry_states_and_long_names_fit_mobile_without_enabling_expired_sharing(self):
        FoodItem.objects.filter(pk=self.food.pk).update(expiration_date=timezone.localdate() - timedelta(days=1))
        FoodItem.objects.filter(name="Apel contoh").update(status="CONSUMED")
        name = "Sayuran segar untuk dibagikan " * 4
        FoodItem.objects.create(
            owner=self.owner, name=name, category="VEGETABLE", status="STORED",
            purchase_date=timezone.localdate(), expiration_date=timezone.localdate(),
        )
        with self.open_inventory(mobile=True) as page:
            for width in [390, 320]:
                page.set_viewport_size({"width": width, "height": 900})
                self.assertTrue(page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
                expired = page.locator(".food-row").filter(has_text="Roti contoh")
                expect(expired.locator(".badge-red")).to_have_text("Sudah kedaluwarsa")
                expect(expired.get_by_role("link", name="Bagikan", exact=True)).to_have_count(0)
                consumed = page.locator(".food-row").filter(has_text="Apel contoh")
                expect(consumed.locator(".badge-gray")).to_have_text("Sudah dikonsumsi")
                expect(consumed.locator(".detail-link")).to_be_visible()
                today = page.locator(".food-row").filter(has_text=name.strip())
                expect(today.locator(".badge-orange")).to_have_text("Hari ini")
                today.locator(".detail-link").click()
                expect(page.get_by_role("dialog").get_by_role("link", name="Bagikan", exact=True)).to_be_visible()
                page.keyboard.press("Escape")
            expired.get_by_role("button", name="Detail Roti contoh", exact=True).click()
            expect(page.locator("#modal-expiration-state")).to_have_text("Sudah kedaluwarsa")
            expect(page.locator("#modal-share-url")).to_be_hidden()
            page.keyboard.press("Escape")
            page.evaluate("window.inventoryTestMarker = 'unchanged'")
            page.once("dialog", lambda dialog: dialog.dismiss())
            expired.get_by_role("link", name="Hapus", exact=True).click()
            expect(expired).to_have_count(1)
            page.once("dialog", lambda dialog: dialog.accept())
            expired.get_by_role("link", name="Hapus", exact=True).click()
            expect(expired).to_have_count(0)
            self.assertEqual(page.evaluate("window.inventoryTestMarker"), "unchanged")

    def test_inventory_keeps_filter_edit_and_delete_fallback_without_javascript(self):
        with self.open_inventory(mobile=True, javascript=False) as page:
            expect(page.locator("#inventory-filters")).to_be_visible()
            expect(page.get_by_role("button", name="Cari dan filter makanan", exact=True)).to_be_hidden()
            page.get_by_label("Cari makanan", exact=True).fill("Roti")
            page.get_by_role("button", name="Tampilkan", exact=True).click()
            expect(page.locator(".food-row")).to_have_count(1)
            row = page.locator(".food-row")
            expect(row.get_by_role("link", name="Edit", exact=True)).to_have_attribute("href", reverse("FoodItem:change_food_item", args=[self.food.pk]))
            row.get_by_role("link", name="Hapus", exact=True).click()
            expect(page.get_by_role("heading", name="Hapus makanan", exact=True)).to_be_visible()
            page.get_by_role("link", name="Batal", exact=True).click()
            expect(page.locator(".food-row")).to_have_count(2)
        self.assertTrue(FoodItem.objects.filter(pk=self.food.pk).exists())
