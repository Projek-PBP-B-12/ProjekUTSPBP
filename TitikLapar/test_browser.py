import os
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from playwright.sync_api import expect, sync_playwright

from FoodItem.models import FoodItem
from Location.models import Location
from SharedPost.models import SharedPost
from notification.models import Notification


class SharedSidebarBrowserTests(StaticLiveServerTestCase):
    def test_logout_position_across_pages_and_notification_actions(self):
        user = get_user_model().objects.create_user(username="sidebar_reader")
        notification = Notification.objects.create(
            recipient=user, title="Pengingat sidebar", message="Periksa makanan di kulkasmu.",
        )
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)
        urls = [
            "landing_page", "sharedpost:list", "FoodItem:makananku",
            "FoodItem:add_food_item", "Location:manage", "userprofile:profile",
            "userprofile:profile_edit", "userprofile:donor_contact", "userprofile:delete_account",
            "notification:show_notification",
        ]
        with sync_playwright() as playwright:
            channel = os.getenv("BROWSER_CHANNEL", "chromium")
            options = {"headless": True}
            if channel != "chromium":
                options["channel"] = channel
            browser = playwright.chromium.launch(**options)
            try:
                context = browser.new_context(reduced_motion="reduce")
                context.add_cookies([{
                    "name": settings.SESSION_COOKIE_NAME,
                    "value": client.cookies[settings.SESSION_COOKIE_NAME].value,
                    "url": self.live_server_url,
                }])
                page = context.new_page()
                # Keep font availability deterministic without depending on Google Fonts.
                page.route("https://fonts.googleapis.com/**", lambda route: route.abort())
                page.route("https://fonts.gstatic.com/**", lambda route: route.abort())
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                desktop_positions = {}
                for url in urls:
                    page.set_viewport_size({"width": 1440, "height": 900})
                    path = reverse(url, args=[user.pk] if url == "userprofile:donor_contact" else None)
                    page.goto(self.live_server_url + path)
                    if url.startswith("userprofile:"):
                        expect(page.locator('.sidebar-item[aria-current="page"]')).to_have_text("Profil")
                    for width in [1440, 801, 800, 390, 320]:
                        page.set_viewport_size({"width": width, "height": 900})
                        toggle = page.locator(".app-menu-toggle")
                        drawer = width <= 800
                        if drawer:
                            expect(toggle).to_be_visible()
                            expect(page.locator("#sidebar")).to_be_hidden()
                            toggle.click()
                            expect(toggle).to_have_attribute("aria-expanded", "true")
                            expect(page.locator("#sidebar")).to_have_attribute("role", "dialog")
                            expect(page.locator(".app-main")).to_have_js_property("inert", True)
                        else:
                            expect(toggle).to_be_hidden()
                        logout = page.locator("#sidebar .sidebar-logout-button")
                        expect(logout).to_be_visible()
                        expect(logout).to_have_count(1)
                        form = page.locator("#sidebar .sidebar-logout")
                        expect(form).to_have_attribute("method", "post")
                        expect(form).to_have_attribute("action", reverse("userprofile:logout"))
                        expect(form.locator('input[name="csrfmiddlewaretoken"]')).to_have_count(1)
                        nav = page.locator("#sidebar .sidebar-nav").bounding_box()
                        box = logout.bounding_box()
                        self.assertAlmostEqual(box["y"] - nav["y"] - nav["height"], 24, delta=1, msg=f"{url}: {width}")
                        self.assertEqual(box["height"], 40)
                        self.assertTrue(page.evaluate("document.documentElement.scrollWidth <= innerWidth"), f"{url}: {width}")
                        if width > 800:
                            if width not in desktop_positions:
                                desktop_positions[width] = box
                            for dimension in ("x", "y", "width", "height"):
                                self.assertAlmostEqual(box[dimension], desktop_positions[width][dimension], delta=1, msg=f"{url}: {width} {dimension}")
                        if url == "notification:show_notification" and width in (1440, 390):
                            output = os.getenv("BROWSER_SCREENSHOT_DIR")
                            if output:
                                Path(output).mkdir(parents=True, exist_ok=True)
                                page.screenshot(path=str(Path(output)/f"notification-sidebar-{width}.png"), full_page=True)
                        if url.startswith("userprofile:") and width in (1440, 390):
                            output = os.getenv("BROWSER_SCREENSHOT_DIR")
                            if output:
                                Path(output).mkdir(parents=True, exist_ok=True)
                                page.screenshot(path=str(Path(output)/f"{url.split(':')[1]}-{width}.png"), full_page=True)
                        if drawer:
                            page.keyboard.press("Escape")
                            expect(toggle).to_have_attribute("aria-expanded", "false")
                            expect(toggle).to_be_focused()
                            expect(page.locator("#sidebar")).to_be_hidden()
                            expect(page.locator(".app-main")).to_have_js_property("inert", False)
                expect(page.locator('.sidebar-item[aria-current="page"]')).to_have_text("Notifikasi")
                expect(page.locator("#notif-unread-count")).to_contain_text("1 belum dibaca")
                page.get_by_role("button", name="Tandai sudah dibaca", exact=True).click()
                expect(page.locator("#notif-unread-count")).to_contain_text("0 belum dibaca")
                expect(page.locator("#notif-feedback")).to_contain_text("berhasil")
                page.locator(".app-menu-toggle").click()
                page.locator("#sidebar .sidebar-logout-button").click()
                expect(page.locator("#sidebar")).to_have_count(0)
                response = page.request.get(self.live_server_url + reverse("notification:show_notification"), max_redirects=0)
                self.assertEqual(response.status, 302)
                self.assertIn(reverse("userprofile:login"), response.headers["location"])
                self.assertEqual(errors, [])
            finally:
                browser.close()
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

    def test_mobile_menu_focus_backdrop_resize_navigation_and_no_script_fallback(self):
        user = get_user_model().objects.create_user(username="menu_reader")
        client = Client()
        client.force_login(user)
        with sync_playwright() as playwright:
            options = {"headless": True}
            channel = os.getenv("BROWSER_CHANNEL", "chromium")
            if channel != "chromium":
                options["channel"] = channel
            browser = playwright.chromium.launch(**options)
            try:
                context = browser.new_context(viewport={"width": 390, "height": 900}, reduced_motion="reduce")
                cookies = [{"name": settings.SESSION_COOKIE_NAME, "value": client.cookies[settings.SESSION_COOKIE_NAME].value, "url": self.live_server_url}]
                context.add_cookies(cookies)
                page = context.new_page()
                page.goto(self.live_server_url + reverse("FoodItem:makananku"))
                menu = page.locator(".app-menu-toggle")
                close = page.locator(".app-menu-close")
                sidebar = page.locator("#sidebar")
                expect(menu).to_have_count(1)
                expect(sidebar).to_be_hidden()
                expect(sidebar).to_have_js_property("inert", True)
                menu.click()
                expect(close).to_be_focused()
                expect(sidebar).to_have_attribute("aria-modal", "true")
                expect(page.locator("body")).to_have_css("overflow", "hidden")
                page.keyboard.press("Shift+Tab")
                expect(sidebar.locator(".sidebar-logout-button")).to_be_focused()
                page.keyboard.press("Tab")
                expect(close).to_be_focused()
                close.click()
                expect(sidebar).to_be_hidden()
                expect(menu).to_be_focused()
                menu.click()
                page.locator(".app-sidebar-backdrop").click(position={"x": 388, "y": 10})
                expect(sidebar).to_be_hidden()
                expect(menu).to_be_focused()
                menu.click()
                page.set_viewport_size({"width": 801, "height": 900})
                expect(sidebar).to_be_visible()
                expect(sidebar).not_to_have_attribute("aria-modal", "true")
                expect(sidebar).to_have_js_property("inert", False)
                expect(menu).to_be_hidden()
                expect(page.locator(".app-main")).to_have_js_property("inert", False)
                page.set_viewport_size({"width": 800, "height": 900})
                expect(sidebar).to_be_hidden()
                expect(menu).to_be_visible()
                menu.click()
                sidebar.get_by_role("link", name="Profil", exact=True).click()
                expect(page).to_have_url(self.live_server_url + reverse("userprofile:profile"))
                expect(sidebar).to_be_hidden()
                expect(menu).to_have_attribute("aria-expanded", "false")
                expect(page.locator(".app-main")).to_have_js_property("inert", False)
                # Tall navigation stays usable in a short landscape viewport.
                page.set_viewport_size({"width": 600, "height": 320})
                menu.click()
                sidebar.locator(".sidebar-logout-button").scroll_into_view_if_needed()
                expect(sidebar.locator(".sidebar-logout-button")).to_be_in_viewport()
                page.keyboard.press("Escape")
                menu.click()
                expect(close).to_be_in_viewport()
                page.keyboard.press("Escape")

                fallback = browser.new_context(java_script_enabled=False, viewport={"width": 320, "height": 900})
                fallback.add_cookies(cookies)
                plain = fallback.new_page()
                plain.goto(self.live_server_url + reverse("FoodItem:makananku"))
                expect(plain.locator("#sidebar")).to_be_visible()
                expect(plain.locator(".app-mobile-header")).to_be_hidden()
                expect(plain.locator(".sidebar-logout-button")).to_be_visible()
            finally:
                browser.close()


class DashboardBrowserTests(StaticLiveServerTestCase):
    def test_dashboard_desktop_mobile_and_links(self):
        user = get_user_model().objects.create_user(username="dashboard_demo", first_name="Jane", last_name="Doe")
        for name, category, days in [("Bayam segar", "VEGETABLE", 1), ("Susu kedelai", "BEVERAGE", 3), ("Apel merah", "FRUIT", 9)]:
            FoodItem.objects.create(owner=user, name=name, category=category, status="STORED",
                                    purchase_date=timezone.localdate(), expiration_date=timezone.localdate()+timedelta(days=days))
        food = FoodItem.objects.create(owner=user, name="Roti berbagi", status="OFFERED",
                                       purchase_date=timezone.localdate(), expiration_date=timezone.localdate()+timedelta(days=9))
        location = Location.objects.create(owner=user, area_name="Beji", latitude="-6.36", longitude="106.83")
        post = SharedPost.objects.create(food_item=food, location=location, description="Ambil di lobi kos sore hari.")
        client = Client()
        client.force_login(user)
        session = client.cookies[settings.SESSION_COOKIE_NAME].value
        with sync_playwright() as playwright:
            channel = os.getenv("BROWSER_CHANNEL", "chromium")
            options = {"headless": os.getenv("BROWSER_HEADLESS", "1") != "0"}
            if channel != "chromium":
                options["channel"] = channel
            browser = playwright.chromium.launch(**options)
            try:
                context = browser.new_context(reduced_motion="reduce")
                context.add_cookies([{"name": settings.SESSION_COOKIE_NAME, "value": session, "url": self.live_server_url}])
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(self.live_server_url + reverse("landing_page"))
                expect(page.get_by_role("heading", name="Selamat Datang, Jane Doe")).to_be_visible()
                expect(page.locator(".summary-value")).to_have_text(["3", "2", "1"])
                expect(page.locator('.sidebar-item[aria-current="page"]')).to_have_text("Beranda")
                expect(page.locator(".dashboard-food-name")).to_have_text(["Bayam segar", "Susu kedelai", "Roti berbagi"])
                heading_font = page.locator(".page-title").evaluate("el => getComputedStyle(el).fontFamily")
                expect(page.locator("#quick-notification-title")).to_have_css("font-family", heading_font)
                for width, columns in [(1440, 3), (900, 3), (801, 3), (800, 3), (640, 3), (390, 1), (320, 1)]:
                    page.set_viewport_size({"width": width, "height": 900})
                    self.assertEqual(page.locator(".dashboard-stats").evaluate("el => getComputedStyle(el).gridTemplateColumns.split(' ').length"), columns)
                    preview_columns = 2 if width >= 1100 else 1
                    self.assertEqual(page.locator(".dashboard-previews").evaluate("el => getComputedStyle(el).gridTemplateColumns.split(' ').length"), preview_columns)
                    self.assertTrue(page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
                    output = os.getenv("BROWSER_SCREENSHOT_DIR")
                    if output:
                        Path(output).mkdir(parents=True, exist_ok=True)
                        page.screenshot(path=str(Path(output)/f"dashboard-{width}.png"), full_page=True)
                page.set_viewport_size({"width": 390, "height": 900})
                menu = page.get_by_role("button", name="Buka menu", exact=True)
                menu.click()
                expect(menu).to_have_attribute("aria-expanded", "true")
                expect(page.locator("#sidebar")).to_be_visible()
                page.keyboard.press("Escape")
                expect(menu).to_have_attribute("aria-expanded", "false")
                page.set_viewport_size({"width": 1440, "height": 900})
                page.get_by_role("link", name="Roti berbagi", exact=False).click()
                expect(page).to_have_url(self.live_server_url + reverse("sharedpost:detail", args=[post.pk]))
                page.goto(self.live_server_url + reverse("landing_page"))
                page.get_by_role("link", name="Sedang dibagikan", exact=False).click()
                expect(page).to_have_url(self.live_server_url + reverse("sharedpost:list") + "?mine=1")
                self.assertEqual(errors, [])
            finally:
                browser.close()

    def test_notification_preview_links_to_inbox(self):
        user = get_user_model().objects.create_user(username="notification_dashboard")
        Notification.objects.create(recipient=user, title="Roti tinggal H-3", message="Konsumsi segera atau bagikan.")
        client = Client()
        client.force_login(user)
        session = client.cookies[settings.SESSION_COOKIE_NAME].value
        with sync_playwright() as playwright:
            channel = os.getenv("BROWSER_CHANNEL", "chromium")
            options = {"headless": True}
            if channel != "chromium": options["channel"] = channel
            browser = playwright.chromium.launch(**options)
            try:
                context = browser.new_context()
                context.add_cookies([{"name": settings.SESSION_COOKIE_NAME, "value": session, "url": self.live_server_url}])
                page = context.new_page()
                page.goto(self.live_server_url + reverse("landing_page"))
                expect(page.get_by_role("heading", name="Belum ada yang perlu segera diperiksa")).to_be_visible()
                expect(page.get_by_role("heading", name="Mulai berbagi dari kulkasmu")).to_be_visible()
                for width in [1440, 390]:
                    page.set_viewport_size({"width": width, "height": 900})
                    self.assertTrue(page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
                    output = os.getenv("BROWSER_SCREENSHOT_DIR")
                    if output:
                        Path(output).mkdir(parents=True, exist_ok=True)
                        page.screenshot(path=str(Path(output)/f"dashboard-empty-{width}.png"), full_page=True)
                page.get_by_role("link", name="Roti tinggal H-3", exact=True).click()
                expect(page).to_have_url(self.live_server_url + reverse("notification:show_notification"))
            finally:
                browser.close()
