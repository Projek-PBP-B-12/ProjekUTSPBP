import os
from pathlib import Path
from contextlib import contextmanager
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone
from playwright.sync_api import expect, sync_playwright

from FoodItem.models import FoodItem
from Location.models import Location
from userprofile.models import UserProfile
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
    def open_board(self, user=None, mobile=False, expected_count=2):
        client = Client()
        client.force_login(user or self.owner)
        session = client.cookies[settings.SESSION_COOKIE_NAME].value
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
                    "value": session, "url": self.live_server_url,
                }])
                page = context.new_page()
                page.set_default_timeout(10000)
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(self.live_server_url + reverse("sharedpost:list"))
                expect(page.locator(".post-card")).to_have_count(expected_count)
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
            expect(page.locator("#board-feedback")).to_have_attribute("data-state", "success")

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

    def test_optimistic_delete_and_complete_update_before_the_server_receives_request(self):
        self.food.status = "OFFERED"
        self.food.save(update_fields=["status"])
        second = SharedPost.objects.create(
            food_item=self.food, location=self.location, description="Ambil di lobi sore hari.",
        )
        with self.open_board(expected_count=3) as (page, navigations):
            for action, post, name, button, remaining in [
                ("delete", self.post, "Susu kedelai", "Hapus", 2),
                ("complete", second, "Roti gandum", "Tandai Sudah Diambil", 1),
            ]:
                with self.subTest(action=action):
                    held = []
                    target = self.live_server_url + reverse(f"sharedpost:{action}", args=[post.pk])
                    page.route(target, lambda route: held.append(route))
                    card = page.locator(".post-card").filter(has=page.locator(".post-title", has_text=name))
                    page.once("dialog", lambda dialog: dialog.accept())
                    with page.expect_request(target):
                        card.get_by_role("button", name=button, exact=True).click()
                    expect(card).to_be_hidden()
                    expect(page.locator(".post-card:visible")).to_have_count(remaining)
                    expect(page.locator("#all-offers-count")).to_have_text(str(remaining))
                    expect(page.locator(".result-count")).to_have_text(f"{remaining} penawaran aktif")
                    expect(page.locator("#board-feedback")).to_have_attribute("data-state", "pending")
                    expect(page.locator("#post-list")).to_have_attribute("aria-busy", "true")
                    expect(page.get_by_role("searchbox")).to_be_disabled()
                    self.assertEqual(len(held), 1)
                    unchanged = page.request.get(self.live_server_url + reverse("sharedpost:detail", args=[post.pk]))
                    self.assertEqual(unchanged.status, 200)
                    self.assertIn("Tersedia", unchanged.text())
                    self.assertNotIn("Penawaran ini sudah tidak tersedia", unchanged.text())
                    held.pop().continue_()
                    expect(card).to_have_count(0)
                    expect(page.locator("#board-feedback")).to_have_attribute("data-state", "success")
                    expect(page.get_by_role("searchbox")).to_be_enabled()
                    expect(page.get_by_role("combobox", name="Radius pencarian")).to_be_disabled()
                    self.assertFalse(page.locator("#post-list").get_attribute("aria-busy"))
                    expect(page.locator("#all-offers-count")).to_have_text(str(remaining))
                    self.assert_no_reload(page, navigations)
        self.assertFalse(SharedPost.objects.filter(pk=self.post.pk).exists())
        second.refresh_from_db()
        self.food.refresh_from_db()
        self.assertFalse(second.is_active)
        self.assertEqual(self.food.status, "CONSUMED")

    def test_optimistic_failures_restore_cards_counts_controls_and_allow_refresh(self):
        with self.open_board(mobile=True) as (page, navigations):
            for action, button in [("delete", "Hapus"), ("complete", "Tandai Sudah Diambil")]:
                target = self.live_server_url + reverse(f"sharedpost:{action}", args=[self.post.pk])
                held = []
                page.route(target, lambda route: held.append(route))
                for failure in [403, 404, 500, "network", "timeout", "abort", "unexpected-html"]:
                    with self.subTest(action=action, failure=failure):
                        card = page.locator(".post-card").filter(has=page.locator(".post-title", has_text="Susu kedelai"))
                        form = card.locator(f'form[data-optimistic-action="{action}"]')
                        form.evaluate("(el, timeout) => el.setAttribute('hx-request', JSON.stringify({timeout}))", 1000 if failure == "timeout" else 15000)
                        page.once("dialog", lambda dialog: dialog.accept())
                        with page.expect_request(target):
                            card.get_by_role("button", name=button, exact=True).click()
                        expect(card).to_be_hidden()
                        expect(page.locator("#all-offers-count")).to_have_text("1")
                        route = held.pop()
                        if isinstance(failure, int):
                            route.fulfill(status=failure, body="Request rejected")
                        elif failure == "network":
                            route.abort("failed")
                        elif failure == "abort":
                            form.evaluate("el => htmx.trigger(el, 'htmx:abort')")
                        elif failure == "unexpected-html":
                            route.fulfill(status=200, body="<h1>Login</h1>")
                        # For timeout the request intentionally stays unanswered.
                        expect(card).to_be_visible()
                        if failure in ["timeout", "abort"]:
                            route.abort()
                        expect(page.locator(".post-card:visible")).to_have_count(2)
                        expect(page.locator("#all-offers-count")).to_have_text("2")
                        expect(page.locator(".result-count")).to_have_text("2 penawaran aktif")
                        expect(page.locator("#board-feedback")).to_have_attribute("data-state", "error")
                        expect(page.locator("#board-feedback")).to_contain_text("Tampilan dipulihkan")
                        expect(card.get_by_role("button", name=button, exact=True)).to_be_enabled()
                        expect(page.get_by_role("searchbox")).to_be_enabled()
                        expect(page.locator("#post-list h1")).to_have_count(0)
                        self.assertTrue(page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
                        self.assert_no_reload(page, navigations)
                page.unroute(target)
            page.get_by_role("button", name="Periksa ulang daftar", exact=True).click()
            expect(page.locator("#post-list.htmx-settling")).to_have_count(0)
            expect(page.locator(".post-card:visible")).to_have_count(2)
            expect(page.locator("#board-feedback")).to_have_text("Daftar penawaran telah diperbarui.")
            self.assert_no_reload(page, navigations)
        self.post.refresh_from_db()
        self.offered_food.refresh_from_db()
        self.assertTrue(self.post.is_active)
        self.assertEqual(self.offered_food.status, "OFFERED")

    def test_cancelling_optimistic_actions_does_not_change_the_board(self):
        with self.open_board() as (page, navigations):
            requests = []
            page.on("request", lambda request: requests.append(request) if request.method == "POST" else None)
            card = page.locator(".post-card").filter(has=page.locator(".post-title", has_text="Susu kedelai"))
            for button in ["Hapus", "Tandai Sudah Diambil"]:
                page.once("dialog", lambda dialog: dialog.dismiss())
                with page.expect_event("dialog"):
                    card.get_by_role("button", name=button, exact=True).click()
                expect(card).to_be_visible()
                expect(page.locator("#all-offers-count")).to_have_text("2")
                expect(page.locator("#board-feedback")).to_be_empty()
            self.assertEqual(requests, [])
            self.assert_no_reload(page, navigations)

    @override_settings(SHAREDPOST_WRITE_LIMIT=1, SHAREDPOST_WRITE_WINDOW_SECONDS=60)
    def test_rate_limit_restores_optimistic_actions_and_keeps_reading_available(self):
        with self.open_board(mobile=True) as (page, navigations):
            # Consume the single slot with an invalid form; no inventory changes.
            panel = self.fill_create(page, description="       pendek       ")
            panel.get_by_role("button", name="Bagikan makanan", exact=True).click()
            expect(panel).to_contain_text("Petunjuk pengambilan minimal 10 karakter.")
            panel.get_by_role("button", name="Batal", exact=True).click()
            card = page.locator(".post-card").filter(has=page.locator(".post-title", has_text="Susu kedelai"))
            for action, button in [("delete", "Hapus"), ("complete", "Tandai Sudah Diambil")]:
                page.once("dialog", lambda dialog: dialog.accept())
                with page.expect_response(self.live_server_url + reverse(f"sharedpost:{action}", args=[self.post.pk])) as result:
                    card.get_by_role("button", name=button, exact=True).click()
                self.assertEqual(result.value.status, 429)
                self.assertTrue(result.value.headers["retry-after"].isdigit())
                expect(card).to_be_visible()
                expect(page.locator("#all-offers-count")).to_have_text("2")
                expect(page.locator("#board-feedback")).to_contain_text("Terlalu banyak perubahan")
                expect(page.locator("#board-feedback")).to_contain_text("Tampilan dipulihkan")
                expect(card.get_by_role("button", name=button, exact=True)).to_be_enabled()
            page.get_by_role("button", name="Periksa ulang daftar", exact=True).click()
            expect(page.locator("#board-feedback")).to_have_text("Daftar penawaran telah diperbarui.")
            expect(page.locator(".post-card:visible")).to_have_count(2)
            self.assert_no_reload(page, navigations)
        self.post.refresh_from_db()
        self.offered_food.refresh_from_db()
        self.assertTrue(self.post.is_active)
        self.assertEqual(self.offered_food.status, "OFFERED")

    @override_settings(SHAREDPOST_WRITE_LIMIT=1, SHAREDPOST_WRITE_WINDOW_SECONDS=60)
    def test_rate_limit_preserves_create_and_edit_form_inputs(self):
        with self.open_board() as (page, navigations):
            panel = self.fill_create(page, description="       pendek       ")
            panel.get_by_role("button", name="Bagikan makanan", exact=True).click()
            expect(panel).to_contain_text("Petunjuk pengambilan minimal 10 karakter.")
            panel.get_by_label("Petunjuk pengambilan").fill("Petunjuk lengkap yang perlu dipertahankan.")
            with page.expect_response(self.live_server_url + reverse("sharedpost:create")) as result:
                panel.get_by_role("button", name="Bagikan makanan", exact=True).click()
            self.assertEqual(result.value.status, 429)
            expect(panel.get_by_label("Petunjuk pengambilan")).to_have_value("Petunjuk lengkap yang perlu dipertahankan.")
            expect(page.locator("#board-feedback")).to_contain_text("Isian form tetap tersimpan")
            expect(panel.get_by_role("button", name="Bagikan makanan", exact=True)).to_be_enabled()
            panel.get_by_role("button", name="Batal", exact=True).click()
            card = page.locator(".post-card").filter(has=page.locator(".post-title", has_text="Susu kedelai"))
            card.locator('a[hx-get]').click()
            panel.get_by_label("Petunjuk pengambilan").fill("Perubahan ini harus tetap ada di form.")
            with page.expect_response(self.live_server_url + reverse("sharedpost:update", args=[self.post.pk])) as result:
                panel.get_by_role("button", name="Simpan perubahan", exact=True).click()
            self.assertEqual(result.value.status, 429)
            expect(panel.get_by_label("Petunjuk pengambilan")).to_have_value("Perubahan ini harus tetap ada di form.")
            self.assert_no_reload(page, navigations)
        self.post.refresh_from_db()
        self.assertEqual(self.post.description, "Ambil di lobi kos sore hari.")

    def test_optimistic_mutation_cancels_stale_filter_read_and_blocks_competing_updates(self):
        with self.open_board() as (page, navigations):
            reads, mutations = [], []
            list_url = self.live_server_url + reverse("sharedpost:list")
            target = self.live_server_url + reverse("sharedpost:delete", args=[self.post.pk])
            def hold_read(route):
                reads.append(route)
                page.evaluate("window.filterReadHeld = true")
            page.route(list_url + "?**", hold_read)
            page.route(target, lambda route: mutations.append(route))
            with page.expect_request(lambda request: request.method == "GET" and request.url.startswith(list_url + "?")):
                page.get_by_role("searchbox").fill("Susu")
            page.wait_for_function("window.filterReadHeld === true")
            self.assertEqual(len(reads), 1)
            card = page.locator(".post-card").filter(has=page.locator(".post-title", has_text="Susu kedelai"))
            page.once("dialog", lambda dialog: dialog.accept())
            with page.expect_request(target), page.expect_event("requestfailed", predicate=lambda request: request.url.startswith(list_url + "?")):
                card.get_by_role("button", name="Hapus", exact=True).click()
            expect(card).to_be_hidden()
            expect(page.locator("#all-offers-count")).to_have_text("1")
            page.evaluate("url => { htmx.ajax('GET', url, {target: '#post-list'}); }", list_url)
            self.assertEqual(len(reads), 1)
            reads.pop().abort()
            self.assertIn("q=Susu", mutations[0].request.post_data)
            mutations.pop().continue_()
            expect(page.locator(".empty-state")).to_be_visible()
            expect(page.locator("#all-offers-count")).to_have_text("0")
            expect(page.get_by_role("searchbox")).to_have_value("Susu")
            expect(page.get_by_role("searchbox")).to_be_enabled()
            self.assert_no_reload(page, navigations)

    def test_search_category_and_own_posts_without_reload(self):
        with self.open_board() as (page, navigations):
            search = page.get_by_role("searchbox", name="Cari makanan atau lokasi")
            search.fill("kukusan")
            expect(page.locator(".post-card")).to_have_count(1)
            expect(page.locator(".post-card")).to_contain_text("Apel merah")
            search.fill("")
            expect(page.locator(".post-card")).to_have_count(2)
            page.get_by_role("radio", name="Beverage", exact=True).check()
            expect(page.locator(".post-card")).to_have_count(1)
            expect(page.locator(".post-card")).to_contain_text("Susu kedelai")
            expect(page.locator(".post-card .category-pill")).to_have_text("Beverage")
            page.get_by_role("radio", name="Semua", exact=True).check()
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
            donor_card.get_by_role("link", name="Klaim Susu kedelai", exact=True).click()
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
            for width, columns in [(1440, 3), (900, 2), (801, 2), (481, 2), (390, 1), (320, 1)]:
                with self.subTest(width=width):
                    page.set_viewport_size({"width": width, "height": 1000})
                    grid = page.locator(".post-grid")
                    expect(grid).to_have_css("display", "grid")
                    actual = grid.evaluate("element => getComputedStyle(element).gridTemplateColumns.split(' ').length")
                    self.assertEqual(actual, columns)
                    self.assertTrue(page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
                    photo = page.locator('.post-card .food-placeholder').first.bounding_box()
                    self.assertAlmostEqual(photo['height'] / photo['width'], 1 / 2, places=2)
                    expect(page.locator('.post-card .area svg').first).to_be_visible()
                    expect(page.locator('.post-card .card-map-link')).to_have_count(2)
                    for link in page.locator('.card-map-link').all():
                        expect(link).to_be_visible()
                    screenshot_dir = os.getenv("BROWSER_SCREENSHOT_DIR")
                    if screenshot_dir:
                        output = Path(screenshot_dir)
                        output.mkdir(parents=True, exist_ok=True)
                        page.screenshot(path=str(output / f"sharedpost-{width}.png"), full_page=True)
            self.assert_no_reload(page, navigations)

    def test_mobile_menu_and_form_fit_screen(self):
        with self.open_board(mobile=True) as (page, navigations):
            menu = page.locator('.app-menu-toggle')
            expect(menu).to_be_visible()
            menu.click()
            expect(menu).to_have_attribute("aria-expanded", "true")
            self.assertGreaterEqual(page.locator("#sidebar").bounding_box()["x"], 0)
            page.locator(".app-menu-close").click()
            expect(menu).to_have_attribute("aria-expanded", "false")
            panel = self.fill_create(page)
            expect(panel).to_be_visible()
            self.assertTrue(page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
            panel.get_by_role("button", name="Batal", exact=True).click()
            self.assert_no_reload(page, navigations)

    def test_figma_filters_distances_load_more_and_claim(self):
        SharedPost.objects.all().delete()
        UserProfile.objects.create(user=self.owner, default_location=self.location)
        examples = [
            ("Roti gandum, masih utuh", "GRAIN", "Beli dua, satu belum dibuka. Ambil di lobi kos putri.", "-6.361000", self.visitor),
            ("Sayur sop siap dimasak", "VEGETABLE", "Wortel, kol, dan buncis. Sudah dicuci bersih.", "-6.362000", self.visitor),
            ("Susu kedelai 2 botol", "BEVERAGE", "Masih tersegel dan selalu disimpan dingin.", "-6.363000", self.visitor),
            ("Nasi putih masih hangat", "GRAIN", "Sisa nasi dari acara kecil, masih bersih dan layak.", "-6.364000", self.visitor),
            ("Apel merah 6 buah", "FRUIT", "Dibeli terlalu banyak, masih segar dan mulus semua.", "-6.365000", self.visitor),
            ("Tempe orek buatan sendiri", "OTHER", "Dimasak semalam, bungkus besar. Siap diambil kapan saja hari ini.", "-6.365500", self.owner),
            ("Roti untuk besok", "GRAIN", "Masih dalam kemasan, ambil sore hari.", "-6.367000", self.visitor),
            ("Roti di luar radius", "GRAIN", "Penawaran lebih jauh untuk menguji radius.", "-6.395000", self.visitor),
        ]
        own_post = None
        for name, category, description, latitude, owner in examples:
            location = Location.objects.create(owner=owner, area_name="Beji", latitude=latitude, longitude="106.830000")
            food = self.make_food(owner, name, category, "OFFERED")
            food.image_url = self.live_server_url + settings.STATIC_URL + "images/landing/food.png"
            food.save(update_fields=["image_url"])
            post = SharedPost.objects.create(food_item=food, location=location, description=description)
            if owner == self.owner:
                own_post = post

        with self.open_board(expected_count=6) as (page, navigations):
            expect(page.locator("#all-offers-count")).to_have_text("7")
            expect(page.get_by_role("combobox", name="Radius pencarian")).to_have_value("2")
            sort = page.get_by_role("combobox", name="Urutkan penawaran")
            expect(sort).to_have_value("nearest")
            expect(sort.locator("option")).to_have_text(["Terdekat", "Terbaru"])
            expect(page.locator(".post-title").first).to_have_text("Roti gandum, masih utuh")
            expect(page.locator(".post-card .area").first).to_contain_text("111 m")
            expect(page.locator(".claim-link")).to_have_count(5)
            for width, columns in [(1440, 3), (900, 2), (481, 2), (390, 1), (320, 1)]:
                page.set_viewport_size({"width": width, "height": 1000})
                self.assertEqual(page.locator(".post-grid").evaluate("el => getComputedStyle(el).gridTemplateColumns.split(' ').length"), columns)
                self.assertTrue(page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
                output = os.getenv("BROWSER_SCREENSHOT_DIR")
                if output:
                    Path(output).mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(Path(output) / f"figma-board-{width}.png"), full_page=True)
            page.set_viewport_size({"width": 1440, "height": 1000})
            expect(page.locator("#post-list.htmx-settling")).to_have_count(0)
            page.get_by_role("link", name="Lihat lebih banyak penawaran", exact=True).click()
            expect(page.locator(".post-card")).to_have_count(7)
            expect(page.locator("#board-page")).to_have_value("2")
            expect(sort).to_have_value("nearest")
            expect(page.locator(".post-title").first).to_have_text("Roti gandum, masih utuh")
            expect(page.locator(".post-title").last).to_have_text("Roti untuk besok")
            expect(page.get_by_role("link", name="Lihat lebih banyak penawaran", exact=True)).to_have_count(0)
            self.assertEqual(page.locator("#board-page").count(), 1)
            self.assertEqual(page.locator("#all-offers-count").count(), 1)

            sort.select_option("newest")
            expect(page.locator("#board-page")).to_have_value("1")
            expect(page.locator(".post-card")).to_have_count(6)
            expect(page.locator(".post-title").first).to_have_text("Roti untuk besok")
            sort.select_option("nearest")
            expect(page.locator(".post-title").first).to_have_text("Roti gandum, masih utuh")

            page.get_by_role("radio", name="Beverage", exact=True).check()
            expect(page.locator(".post-card")).to_have_count(1)
            expect(page.locator("#board-page")).to_have_value("1")
            expect(page.locator("#all-offers-count")).to_have_text("1")
            page.get_by_role("radio", name="Semua", exact=True).check()
            expect(page.locator(".post-card")).to_have_count(6)

            page.get_by_role("combobox", name="Radius pencarian").select_option("")
            expect(page.locator("#all-offers-count")).to_have_text("8")
            expect(page.locator(".post-title").first).to_have_text("Roti gandum, masih utuh")
            sort.select_option("newest")
            expect(page.locator(".post-title").first).to_have_text("Roti di luar radius")
            page.get_by_role("combobox", name="Radius pencarian").select_option("1")
            expect(page.locator("#all-offers-count")).to_have_text("7")
            expect(page.locator(".post-title").first).to_have_text("Roti untuk besok")

            expect(page.locator("#post-list.htmx-settling")).to_have_count(0)
            page.get_by_role("link", name="Lihat lebih banyak penawaran", exact=True).click()
            expect(page.locator(".post-card")).to_have_count(7)
            card = page.locator(".post-card").filter(has=page.get_by_role("heading", name="Tempe orek buatan sendiri", exact=True))
            page.once("dialog", lambda dialog: dialog.accept())
            card.get_by_role("button", name="Hapus", exact=True).click()
            expect(page.locator(".post-card")).to_have_count(6)
            expect(page.locator("#all-offers-count")).to_have_text("6")
            expect(page.locator("#board-page")).to_have_value("1")
            expect(page.get_by_role("combobox", name="Radius pencarian")).to_have_value("1")
            expect(sort).to_have_value("newest")
            self.assert_no_reload(page, navigations)

            page.get_by_role("link", name="Klaim Roti gandum, masih utuh", exact=True).click()
            expect(page.get_by_role("link", name="Hubungi donor", exact=True)).to_be_visible()
            page.get_by_role("link", name="Hubungi donor", exact=True).click()
            expect(page).to_have_url(self.live_server_url + reverse("userprofile:donor_contact", args=[self.visitor.pk]))
        self.assertFalse(SharedPost.objects.filter(pk=own_post.pk).exists())

    def test_nearest_is_disabled_without_origin_while_newest_remains_usable(self):
        with self.open_board(mobile=True) as (page, navigations):
            sort = page.get_by_role("combobox", name="Urutkan penawaran")
            expect(sort).to_be_enabled()
            expect(sort).to_have_value("newest")
            expect(sort.locator('option[value="nearest"]')).to_have_js_property("disabled", True)
            expect(sort.locator('option[value="newest"]')).to_have_js_property("disabled", False)
            expect(sort.locator("option")).to_have_text(["Terdekat", "Terbaru"])
            expect(page.locator(".post-title").first).to_have_text("Apel merah")
            page.get_by_role("searchbox", name="Cari makanan atau lokasi").fill("Susu")
            expect(page.locator(".post-card")).to_have_count(1)
            expect(sort).to_have_value("newest")
            self.assertTrue(page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
            self.assert_no_reload(page, navigations)

    def stub_map_provider(self, page):
        # Stub only the external Leaflet API, so the integration is independent of CDN/tile availability.
        leaflet = """
          window.mapTest = {views: [], markers: []};
          window.L = {
            map: function () {
              document.getElementById('map').style.position = 'relative';
              const map = {
                zoomControl: {setPosition: function () {}},
                setView: function (point, zoom) {window.mapTest.views.push({point, zoom}); return map;},
                closePopup: function () {document.querySelector('.map-popup')?.remove();},
                on: function () {return map;},
                flyTo: function () {}, fitBounds: function () {}
              };
              return map;
            },
            tileLayer: function () {return {addTo: function () {}};},
            divIcon: function (options) {return options;},
            marker: function (point, options) {
              let content;
              let icon;
              const marker = {
                addTo: function () {
                  icon = document.createElement('div'); icon.className = options.icon.className;
                  icon.textContent = options.icon.html; icon.setAttribute('role', 'button');
                  icon.setAttribute('aria-label', options.alt); icon.tabIndex = 0;
                  icon.style.width = '36px'; icon.style.height = '36px';
                  icon.addEventListener('click', function () {marker.openPopup();});
                  document.getElementById('map').append(icon);
                  window.mapTest.markers.push({point, label: options.title}); return marker;
                },
                bindPopup: function (node) {content = node; return marker;},
                getLatLng: function () {return point;},
                getElement: function () {return icon;},
                openPopup: function () {
                  document.querySelector('.map-popup')?.remove();
                  const popup = document.createElement('div'); popup.className = 'map-popup';
                  popup.style.cssText = 'position:absolute;top:48px;left:8px;width:272px;max-width:calc(100% - 16px)';
                  const wrapper = document.createElement('div'); wrapper.className = 'leaflet-popup-content-wrapper';
                  const body = document.createElement('div'); body.className = 'leaflet-popup-content';
                  body.append(content); wrapper.append(body); popup.append(wrapper);
                  document.getElementById('map').append(popup); return marker;
                }
              };
              return marker;
            }
          };
        """
        page.route("**/leaflet.min.js", lambda route: route.fulfill(body=leaflet, content_type="application/javascript"))
        page.route("**/leaflet.min.css", lambda route: route.fulfill(body="", content_type="text/css"))

    def test_detail_location_opens_the_selected_offer_on_map(self):
        with self.open_board(user=self.visitor) as (page, navigations):
            self.stub_map_provider(page)
            page.goto(self.live_server_url + reverse("sharedpost:detail", args=[self.post.pk]))
            for width in [1440, 390]:
                page.set_viewport_size({"width": width, "height": 900})
                expect(page.get_by_role("heading", name="Lokasi umum", exact=True)).to_be_visible()
                expect(page.get_by_role("link", name="Lihat lokasi Susu kedelai di peta", exact=True)).to_be_visible()
                self.assertTrue(page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
                output = os.getenv("BROWSER_SCREENSHOT_DIR")
                if output:
                    Path(output).mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(Path(output) / f"detail-location-{width}.png"), full_page=True)
            page.get_by_role("link", name="Lihat lokasi Susu kedelai di peta", exact=True).click()
            expect(page).to_have_url(self.live_server_url + reverse("Location:map") + f"?post={self.post.pk}")
            expect(page.locator(".map-pin-selected")).to_have_count(1)
            expect(page.locator(".map-popup-title")).to_have_text("Susu kedelai")
            expect(page.locator("#map-search-hint")).to_contain_text("Menampilkan area penawaran Susu kedelai")
            self.assertEqual(page.evaluate("window.mapTest.views.at(-1)"), {"point": [-6.36, 106.83], "zoom": 16})

            # Kartu sendiri maupun milik donor membuka pin yang sesuai setelah filter HTMX.
            for name in ["Susu kedelai", "Apel merah"]:
                page.goto(self.live_server_url + reverse("sharedpost:list"))
                page.set_viewport_size({"width": 390, "height": 900})
                page.get_by_role("searchbox", name="Cari makanan atau lokasi").fill(name)
                expect(page.locator(".post-card")).to_have_count(1)
                link = page.get_by_role("link", name=f"Lihat lokasi {name} di peta", exact=True)
                target = link.get_attribute("href")
                link.focus()
                expect(link).to_be_focused()
                link.press("Enter")
                expect(page).to_have_url(self.live_server_url + target)
                expect(page.locator(".map-pin-selected")).to_have_count(1)
                expect(page.locator(".map-popup-title")).to_have_text(name)

    def test_overlapping_map_offers_remain_accessible_in_one_scrollable_popup(self):
        # Distinct private points can round to the same public point, too.
        nearby = Location.objects.create(
            owner=self.owner, area_name="Beji", latitude="-6.360200", longitude="106.830200",
        )
        offers = [self.post]
        for index in range(6):
            title = f"Makanan berbagi {index}" if index else '<img src=x onerror="window.popupInjected=true">'
            food = self.make_food(self.owner, title, "OTHER", "OFFERED")
            offers.append(SharedPost.objects.create(
                food_item=food, location=nearby if index % 2 else self.location,
                description="<script>window.popupInjected=true</script> Ambil di lobi.",
            ))
        with self.open_board(user=self.visitor, expected_count=6) as (page, navigations):
            self.stub_map_provider(page)
            page.goto(self.live_server_url + reverse("Location:map") + f"?post={self.post.pk}")
            expect(page.locator(".map-pin")).to_have_count(2)
            self.assertCountEqual(page.locator(".map-pin").all_text_contents(), ["7", "1"])
            expect(page.locator(".map-pin-selected")).to_have_text("7")
            expect(page.locator(".map-popup-heading")).to_have_text("7 penawaran di area ini")
            expect(page.locator(".map-popup-offer")).to_have_count(7)
            expect(page.locator(".map-popup-title").first).to_have_text("Susu kedelai")
            expect(page.locator(".map-popup-offer-selected .map-popup-title")).to_have_text("Susu kedelai")
            for offer in offers:
                link = page.locator(".map-popup").get_by_role("link", name=f"Lihat penawaran {offer.food_item.name}", exact=True)
                expect(link).to_have_attribute("href", reverse("sharedpost:detail", args=[offer.pk]))
            expect(page.locator(".map-popup img, .map-popup script")).to_have_count(0)
            self.assertIsNone(page.evaluate("window.popupInjected"))
            region = page.get_by_role("region", name="Daftar penawaran di titik ini")
            for width in [1440, 390, 320]:
                page.set_viewport_size({"width": width, "height": 844})
                self.assertTrue(region.evaluate("el => el.scrollHeight > el.clientHeight"))
                self.assertTrue(page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
                region.focus()
                region.press("End")
                region.scroll_into_view_if_needed()
                expect(page.locator(".map-popup-claim").last).to_be_in_viewport()
                page.locator(".map-popup").scroll_into_view_if_needed()
                expect(page.locator(".map-popup")).to_be_in_viewport(ratio=0.99)
                page.wait_for_function("""() => {
                    const popup = document.querySelector('.map-popup').getBoundingClientRect();
                    const map = document.getElementById('map').getBoundingClientRect();
                    return popup.left >= map.left && popup.right <= map.right
                        && popup.top >= map.top && popup.bottom <= map.bottom;
                }""")
                output = os.getenv("BROWSER_SCREENSHOT_DIR")
                if output:
                    Path(output).mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(Path(output) / f"map-group-{width}.png"), full_page=True)
            page.locator("#map-reset-center").click()
            page.locator("#map-show-all").click()
            page.get_by_role("button", name="1 penawaran di area Kukusan", exact=True).click()
            expect(page.locator(".map-popup-offer")).to_have_count(1)
            expect(page.locator(".map-popup-title")).to_have_text("Apel merah")
            page.locator("#map-reset-center").click()
            page.locator("#map-show-all").click()
            page.get_by_role("button", name="7 penawaran di area Beji", exact=True).click()
            expect(page.locator(".map-popup-offer")).to_have_count(7)
            link = page.locator(".map-popup-claim").last
            target = link.get_attribute("href")
            link.click()
            expect(page).to_have_url(self.live_server_url + target)
