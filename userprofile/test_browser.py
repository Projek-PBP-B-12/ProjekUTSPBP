"""Interaksi halaman akun pada layout bersama, memakai database tes sementara."""
import os
from contextlib import contextmanager

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client
from django.urls import reverse
from playwright.sync_api import expect, sync_playwright

from Location.models import Location
from .models import UserProfile


class ProfileLayoutBrowserTests(StaticLiveServerTestCase):
    password = "Q7!mango-river-planet"

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="profile_browser", email="owner@example.com", password=self.password,
        )
        self.location = Location.objects.create(
            owner=self.user, area_name="Kampus", latitude="-6.360000", longitude="106.830000",
        )
        UserProfile.objects.create(user=self.user)
        self.other = get_user_model().objects.create_user(
            username="other_donor", email="private@example.com",
        )
        UserProfile.objects.create(user=self.other, whatsapp_number="6281234567890", line_id="donor.line")

    @contextmanager
    def open_page(self, name):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        with sync_playwright() as playwright:
            options = {"headless": True}
            channel = os.getenv("BROWSER_CHANNEL", "chromium")
            if channel != "chromium":
                options["channel"] = channel
            browser = playwright.chromium.launch(**options)
            try:
                context = browser.new_context(viewport={"width": 390, "height": 900}, reduced_motion="reduce")
                context.add_cookies([{
                    "name": settings.SESSION_COOKIE_NAME,
                    "value": client.cookies[settings.SESSION_COOKIE_NAME].value,
                    "url": self.live_server_url,
                }])
                page = context.new_page()
                # No external assets are required to verify the account forms.
                page.route("**/*", lambda route: route.continue_() if route.request.url.startswith(self.live_server_url) else route.abort())
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(self.live_server_url + reverse(name))
                yield page
                self.assertEqual(errors, [])
            finally:
                browser.close()

    def test_profile_validation_save_and_private_donor_contact(self):
        with self.open_page("userprofile:profile_edit") as page:
            main = page.locator(".profile-main")
            expect(page.locator("#sidebar")).to_have_count(1)
            expect(page.locator(".sidebar-logout-button")).to_have_count(1)
            main.get_by_role("textbox", name="Email pengingat", exact=True).fill("bukan-email")
            main.get_by_label("ID Line", exact=False).fill("kontak.baru")
            main.get_by_role("button", name="Simpan perubahan", exact=True).click()
            expect(page.get_by_role("alert")).to_contain_text("Profil belum disimpan")
            expect(main.get_by_role("textbox", name="Email pengingat", exact=True)).to_have_value("bukan-email")
            expect(main.get_by_label("ID Line", exact=False)).to_have_value("kontak.baru")
            main.get_by_role("textbox", name="Email pengingat", exact=True).fill("updated@example.com")
            main.get_by_label("Nomor WhatsApp", exact=False).fill("6281122233344")
            main.get_by_label("Lokasi bawaan peta", exact=False).select_option(str(self.location.pk))
            main.get_by_role("button", name="Simpan perubahan", exact=True).click()
            expect(page).to_have_url(self.live_server_url + reverse("userprofile:profile"))
            expect(page.locator(".app-messages p")).to_have_text(["Profil berhasil diperbarui."])
            expect(main).to_contain_text("updated@example.com")
            expect(main).to_contain_text("kontak.baru")
            expect(main).to_contain_text("Kampus")
            self.assertTrue(page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
            page.goto(self.live_server_url + reverse("userprofile:donor_contact", args=[self.other.pk]))
            expect(main).to_contain_text("donor.line")
            expect(page.locator("body")).not_to_contain_text("private@example.com")
            expect(main.get_by_role("link", name="Hubungi via WhatsApp", exact=False)).to_have_attribute("href", "https://wa.me/6281234567890")
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "updated@example.com")
        self.assertEqual(self.user.profile.line_id, "kontak.baru")
        self.assertEqual(self.user.profile.default_location_id, self.location.pk)

    def test_delete_confirmation_layout_and_password_validation(self):
        with self.open_page("userprofile:delete_account") as page:
            page.set_viewport_size({"width": 320, "height": 900})
            main = page.locator(".profile-main")
            checkbox = main.get_by_role("checkbox")
            expect(checkbox).not_to_be_checked()
            self.assertEqual(checkbox.bounding_box()["width"], 18)
            self.assertEqual(checkbox.bounding_box()["height"], 18)
            self.assertTrue(page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
            main.get_by_label("Kata sandi saat ini", exact=True).fill("wrong-password")
            checkbox.check()
            main.get_by_role("button", name="Hapus akun permanen", exact=True).click()
            expect(page.get_by_role("alert")).to_contain_text("Akun belum dihapus")
            expect(main).to_contain_text("Kata sandi tidak sesuai")
            self.assertEqual(page.request.get(self.live_server_url + reverse("userprofile:profile")).status, 200)
            main.get_by_role("link", name="Batal", exact=True).click()
            expect(page).to_have_url(self.live_server_url + reverse("userprofile:profile"))
            main.get_by_role("link", name="Tinjau penghapusan akun", exact=True).click()
            expect(checkbox).not_to_be_checked()
            main.get_by_label("Kata sandi saat ini", exact=True).fill(self.password)
            checkbox.check()
            main.get_by_role("button", name="Hapus akun permanen", exact=True).click()
            expect(page).to_have_url(self.live_server_url + reverse("landing_page"))
            expect(page.locator("#sidebar")).to_have_count(0)
        self.assertFalse(get_user_model().objects.filter(pk=self.user.pk).exists())
        self.assertTrue(get_user_model().objects.filter(pk=self.other.pk).exists())
