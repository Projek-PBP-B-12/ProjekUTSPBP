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
