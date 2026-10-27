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

from FoodItem.models import FoodItem
from Location.models import Location
from .models import SharedPost


class SharedPostBrowserTests(StaticLiveServerTestCase):
    def setUp(self):
        super().setUp()
        self.owner = get_user_model().objects.create_user(username="browser_donor")
        self.visitor = get_user_model().objects.create_user(username="browser_visitor")
        self.location = Location.objects.create(
            owner=self.owner, area_name="Beji",
            latitude="-6.360000", longitude="106.830000",
        )
        visitor_location = Location.objects.create(
            owner=self.visitor, area_name="Kukusan",
            latitude="-6.370000", longitude="106.820000",
        )
        self.food = self.make_food(self.owner, "Roti gandum", "GRAIN", "STORED")
        self.offered_food = self.make_food(self.owner, "Susu kedelai", "BEVERAGE", "OFFERED")
        visitor_food = self.make_food(self.visitor, "Apel merah", "FRUIT", "OFFERED")
        self.post = SharedPost.objects.create(
            food_item=self.offered_food, location=self.location,
            description="Ambil di lobi kos sore hari.",
        )
        SharedPost.objects.create(
            food_item=visitor_food, location=visitor_location,
            description="Ambil di pos satpam sebelum malam.",
        )

    def make_food(self, owner, name, category, status):
        return FoodItem.objects.create(
            owner=owner, name=name, category=category, status=status,
            purchase_date=timezone.localdate(),
            expiration_date=timezone.localdate() + timedelta(days=3),
        )

    @contextmanager
    def open_board(self, user=None, mobile=False):
        client = Client()
        client.force_login(user or self.owner)
        session = client.cookies[settings.SESSION_COOKIE_NAME].value
        with sync_playwright() as playwright:
            options = {"headless": os.getenv("BROWSER_HEADLESS", "1") != "0"}
            channel = os.getenv("BROWSER_CHANNEL", "msedge")
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
                    "value": session, "url": self.live_server_url,
                }])
                page = context.new_page()
                page.set_default_timeout(10000)
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(self.live_server_url + reverse("sharedpost:list"))
                expect(page.locator(".post-card")).to_have_count(2)
                navigations = []
                page.on("framenavigated", lambda frame: navigations.append(frame.url) if frame == page.main_frame else None)
                page.evaluate("window.testMarker = 'same-document'")
                yield page, navigations
                self.assertEqual(errors, [], "Kesalahan JavaScript di browser")
            finally:
                browser.close()

    def assert_no_reload(self, page, navigations):
        self.assertEqual(navigations, [])
        self.assertEqual(page.evaluate("window.testMarker"), "same-document")

    def fill_create(self, page, description="Ambil di lobi pukul lima sore."):
        page.get_by_role("link", name="+ Buat Penawaran", exact=True).click()
        panel = page.locator("#post-form")
        panel.get_by_label("Makanan yang dibagikan").select_option(str(self.food.pk))
        panel.get_by_label("Lokasi pengambilan").select_option(str(self.location.pk))
        panel.get_by_label("Petunjuk pengambilan").fill(description)
        return panel

    def test_htmx_create_edit_delete_and_complete_without_reload(self):
        with self.open_board() as (page, navigations):
            panel = self.fill_create(page)
            panel.get_by_role("button", name="Bagikan makanan", exact=True).click()
            card = page.locator(".post-card").filter(has=page.get_by_role("heading", name="Roti gandum", exact=True))
            expect(card).to_have_count(1)
            expect(panel).to_contain_text("Penawaran berhasil ditambahkan.")

            card.locator('a[hx-get]').click()
            expect(panel.get_by_label("Makanan yang dibagikan")).to_be_disabled()
            panel.get_by_label("Petunjuk pengambilan").fill("Petunjuk baru: ambil di pos satpam.")
            panel.get_by_role("button", name="Simpan perubahan").click()
            expect(card).to_contain_text("Petunjuk baru: ambil di pos satpam.")

            page.once("dialog", lambda dialog: dialog.dismiss())
            with page.expect_event("dialog"):
                card.get_by_role("button", name="Hapus", exact=True).click()
            expect(card).to_have_count(1)
            page.once("dialog", lambda dialog: dialog.accept())
            card.get_by_role("button", name="Hapus", exact=True).click()
            expect(card).to_have_count(0)

            panel = self.fill_create(page)
            panel.get_by_role("button", name="Bagikan makanan", exact=True).click()
            expect(card).to_have_count(1)
            page.once("dialog", lambda dialog: dialog.accept())
            card.get_by_role("button", name="Tandai Sudah Diambil").click()
            expect(card).to_have_count(0)
            self.assert_no_reload(page, navigations)

        self.food.refresh_from_db()
        self.assertEqual(self.food.status, "CONSUMED")
        completed = SharedPost.objects.get(food_item=self.food)
        self.assertFalse(completed.is_active)
        self.assertEqual(completed.description, "Ambil di lobi pukul lima sore.")

    def test_server_validation_and_cancel_without_reload(self):
        with self.open_board() as (page, navigations):
            panel = self.fill_create(page, description="       pendek       ")
            panel.get_by_role("button", name="Bagikan makanan", exact=True).click()
            expect(panel).to_contain_text("Petunjuk pengambilan minimal 10 karakter.")
            expect(panel.get_by_label("Petunjuk pengambilan")).to_have_value("       pendek       ")
            expect(page.locator(".post-card")).to_have_count(2)
            panel.get_by_role("button", name="Batal", exact=True).click()
            expect(panel.locator("form")).to_have_count(0)
            self.assert_no_reload(page, navigations)
        self.assertFalse(SharedPost.objects.filter(food_item=self.food).exists())
        self.food.refresh_from_db()
        self.assertEqual(self.food.status, "STORED")

    def test_search_category_and_own_posts_without_reload(self):
        with self.open_board() as (page, navigations):
            search = page.get_by_role("searchbox", name="Cari makanan atau lokasi")
            search.fill("kukusan")
            expect(page.locator(".post-card")).to_have_count(1)
            expect(page.locator(".post-card")).to_contain_text("Apel merah")
            search.fill("")
            expect(page.locator(".post-card")).to_have_count(2)
            page.get_by_role("combobox", name="Kategori", exact=True).select_option("BEVERAGE")
            expect(page.locator(".post-card")).to_have_count(1)
            expect(page.locator(".post-card")).to_contain_text("Susu kedelai")
            page.get_by_role("combobox", name="Kategori", exact=True).select_option("")
            expect(page.locator(".post-card")).to_have_count(2)
            page.get_by_text("Penawaran Saya", exact=True).click()
            expect(page.locator(".post-card")).to_have_count(1)
            expect(page.locator(".post-card")).to_contain_text("Susu kedelai")
            search.fill("tidak ditemukan")
            expect(page.locator(".empty-state")).to_be_visible()
            self.assert_no_reload(page, navigations)

    def test_visitor_detail_and_mutation_permissions(self):
        with self.open_board(user=self.visitor) as (page, navigations):
            donor_card = page.locator(".post-card").filter(has=page.get_by_role("heading", name="Susu kedelai", exact=True))
            expect(donor_card.locator('a[hx-get]')).to_have_count(0)
            expect(donor_card.get_by_role("button")).to_have_count(0)
            page.get_by_role("link", name="+ Buat Penawaran", exact=True).click()
            csrf = page.locator("#post-form input[name=csrfmiddlewaretoken]").input_value()
            for action in ["delete", "complete", "update"]:
                response = page.request.post(
                    self.live_server_url + reverse(f"sharedpost:{action}", args=[self.post.pk]),
                    form={"description": "Perubahan tidak berizin."},
                    headers={"X-CSRFToken": csrf, "Referer": page.url},
                )
                self.assertEqual(response.status, 404)
            self.assert_no_reload(page, navigations)
            donor_card.get_by_role("link", name="Lihat detail").click()
            expect(page).to_have_url(self.live_server_url + reverse("sharedpost:detail", args=[self.post.pk]))
            expect(page.get_by_role("heading", name="Susu kedelai")).to_be_visible()
            expect(page.get_by_text("Ambil di lobi kos sore hari.", exact=True)).to_be_visible()
            expect(page.get_by_role("link", name="Edit penawaran")).to_have_count(0)
        self.post.refresh_from_db()
        self.offered_food.refresh_from_db()
        self.assertTrue(self.post.is_active)
        self.assertEqual(self.post.description, "Ambil di lobi kos sore hari.")
        self.assertEqual(self.offered_food.status, "OFFERED")

    def test_responsive_grid_uses_tailwind_breakpoints(self):
        with self.open_board() as (page, navigations):
            for width, columns in [(1440, 3), (900, 2), (390, 1)]:
                with self.subTest(width=width):
                    page.set_viewport_size({"width": width, "height": 1000})
                    grid = page.locator(".post-grid")
                    expect(grid).to_have_css("display", "grid")
                    actual = grid.evaluate("element => getComputedStyle(element).gridTemplateColumns.split(' ').length")
                    self.assertEqual(actual, columns)
                    self.assertTrue(page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
                    photo = page.locator('.post-card .food-placeholder').first.bounding_box()
                    self.assertAlmostEqual(photo['height'] / photo['width'], 10 / 16, places=2)
                    expect(page.locator('.post-card .area svg').first).to_be_visible()
                    screenshot_dir = os.getenv("BROWSER_SCREENSHOT_DIR")
                    if screenshot_dir:
                        output = Path(screenshot_dir)
                        output.mkdir(parents=True, exist_ok=True)
                        page.screenshot(path=str(output / f"sharedpost-{width}.png"), full_page=True)
            self.assert_no_reload(page, navigations)

    def test_mobile_menu_and_form_fit_screen(self):
        with self.open_board(mobile=True) as (page, navigations):
            menu = page.locator('.menu-toggle')
            expect(menu).to_be_visible()
            menu.click()
            expect(menu).to_have_attribute("aria-expanded", "true")
            self.assertGreaterEqual(page.locator("#sidebar").bounding_box()["x"], 0)
            page.locator(".menu-close").click()
            expect(menu).to_have_attribute("aria-expanded", "false")
            panel = self.fill_create(page)
            expect(panel).to_be_visible()
            self.assertTrue(page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
            panel.get_by_role("button", name="Batal", exact=True).click()
            self.assert_no_reload(page, navigations)
