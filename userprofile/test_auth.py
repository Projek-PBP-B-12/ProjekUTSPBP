"""Tes tahap 2: sesi login/logout dan akses profil milik sendiri.

Jalankan semua tes app dengan ``python manage.py test userprofile``.
Database tes terpisah dari database yang dipakai saat menjalankan aplikasi.
"""

from decimal import Decimal
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils.html import escape

from userprofile.models import UserProfile


User = get_user_model()


class AccountTestCase(TestCase):
    """Data awal dipakai ulang; setiap tes tetap mendapat database terisolasi."""

    password = "Q7!mango-river-planet"

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="pemilik_akun", password=cls.password
        )
        cls.profile = UserProfile.objects.create(
            user=cls.user,
            whatsapp_number="6281234567890",
            line_id="pemilik.line",
            default_latitude=Decimal("-6.360000"),
            default_longitude=Decimal("106.820000"),
        )

    def setUp(self):
        self.login_url = reverse("userprofile:login")
        self.logout_url = reverse("userprofile:logout")
        self.profile_url = reverse("userprofile:profile")
        self.credentials = {
            "username": self.user.username,
            "password": self.password,
        }


class LoginTests(AccountTestCase):
    def test_login_page_has_credentials_fields_and_csrf_token(self):
        response = self.client.get(self.login_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "userprofile/login.html")
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="password"')
        self.assertContains(response, 'autocomplete="current-password"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_correct_credentials_create_session_and_open_own_profile(self):
        response = self.client.post(self.login_url, self.credentials)

        self.assertRedirects(response, self.profile_url)
        self.assertEqual(self.client.session["_auth_user_id"], str(self.user.pk))
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(UserProfile.objects.count(), 1)

    def test_safe_next_destination_is_preserved_and_used_after_login(self):
        destination = reverse("landing_page") + "?asal=profil"
        response = self.client.get(self.login_url, {"next": destination})

        self.assertEqual(response.context["next"], destination)
        self.assertContains(response, 'name="next"')
        response = self.client.post(
            self.login_url, self.credentials | {"next": destination}
        )

        self.assertRedirects(response, destination)

    def test_unsafe_next_destinations_cannot_redirect_users_outside_the_site(self):
        # ``next`` datang dari browser, jadi tidak boleh langsung dipercaya.
        for destination in (
            "https://evil.example/ambil-akun",
            "//evil.example/ambil-akun",
            "javascript:alert(1)",
        ):
            with self.subTest(destination=destination):
                client = Client()
                response = client.post(
                    self.login_url, self.credentials | {"next": destination}
                )

                self.assertRedirects(response, self.profile_url)
                self.assertEqual(client.session["_auth_user_id"], str(self.user.pk))

    def test_https_login_rejects_next_destination_using_plain_http(self):
        response = self.client.post(
            self.login_url,
            self.credentials | {"next": "http://testserver/accounts/profile/"},
            secure=True,
        )

        self.assertRedirects(response, self.profile_url)

    def test_invalid_and_inactive_accounts_have_same_error_without_password_echo(self):
        inactive = User.objects.create_user(
            username="akun_nonaktif", password=self.password, is_active=False
        )
        errors = []
        for credentials in (
            self.credentials | {"password": "kata-sandi-yang-salah"},
            self.credentials | {"username": "akun_tidak_ada"},
            self.credentials | {"username": inactive.username},
        ):
            with self.subTest(username=credentials["username"]):
                response = self.client.post(self.login_url, credentials)

                self.assertEqual(response.status_code, 200)
                errors.append(list(response.context["form"].non_field_errors()))
                self.assertTrue(errors[-1])
                self.assertNotContains(response, credentials["password"])
                self.assertNotIn("_auth_user_id", self.client.session)

        # Pesan seragam menghindari pembocoran keberadaan/status akun.
        self.assertEqual(errors[0], errors[1])
        self.assertEqual(errors[0], errors[2])

    def test_login_without_valid_csrf_token_is_rejected(self):
        client = Client(enforce_csrf_checks=True)
        client.get(self.login_url)

        for extra_fields in ({}, {"csrfmiddlewaretoken": "token-tidak-valid"}):
            with self.subTest(extra_fields=extra_fields):
                response = client.post(self.login_url, self.credentials | extra_fields)

                self.assertEqual(response.status_code, 403)
                self.assertNotIn("_auth_user_id", client.session)

    def test_login_with_valid_csrf_token_succeeds(self):
        client = Client(enforce_csrf_checks=True)
        client.get(self.login_url)
        token = client.cookies["csrftoken"].value

        response = client.post(
            self.login_url, self.credentials | {"csrfmiddlewaretoken": token}
        )

        self.assertRedirects(response, self.profile_url)
        self.assertEqual(client.session["_auth_user_id"], str(self.user.pk))

    def test_logged_in_user_is_redirected_away_from_login(self):
        self.client.force_login(self.user)

        response = self.client.get(self.login_url)

        self.assertRedirects(response, self.profile_url)

    def test_next_pointing_back_to_login_falls_back_to_profile_without_redirect_loop(self):
        # next bisa menunjuk halaman login sendiri, termasuk melalui URL absolut.
        for destination in (
            self.login_url,
            self.login_url + "?asal=profil",
            "http://testserver" + self.login_url,
        ):
            with self.subTest(destination=destination):
                client = Client()
                response = client.post(
                    self.login_url, self.credentials | {"next": destination}
                )
                self.assertRedirects(response, self.profile_url)

                # Kunjungan ulang saat sudah login juga harus aman dari loop/500.
                response = client.get(self.login_url, {"next": destination})
                self.assertRedirects(response, self.profile_url)

    def test_unsupported_methods_cannot_login(self):
        for method in ("PUT", "PATCH", "DELETE"):
            with self.subTest(method=method):
                response = self.client.generic(method, self.login_url)

                self.assertEqual(response.status_code, 405)
                self.assertNotIn("_auth_user_id", self.client.session)


class OwnProfileTests(AccountTestCase):
    def test_anonymous_user_is_sent_to_login_with_return_destination(self):
        response = self.client.get(self.profile_url)

        self.assertEqual(response.status_code, 302)
        destination = urlsplit(response["Location"])
        self.assertEqual(destination.path, self.login_url)
        self.assertEqual(parse_qs(destination.query), {"next": [self.profile_url]})
        self.assertIn("no-store", response["Cache-Control"])

    def test_profile_uses_session_owner_even_when_another_user_id_is_supplied(self):
        other_user = User.objects.create_user(username="pengguna_lain")
        other_profile = UserProfile.objects.create(
            user=other_user, whatsapp_number="6289876543210", line_id="line.rahasia"
        )
        self.client.force_login(self.user)

        response = self.client.get(self.profile_url, {"user_id": other_user.pk})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "userprofile/profile.html")
        self.assertEqual(response.context["profile"], self.profile)
        self.assertContains(response, self.user.username)
        self.assertContains(response, self.profile.whatsapp_number)
        self.assertContains(response, self.profile.line_id)
        self.assertNotContains(response, other_profile.whatsapp_number)
        self.assertNotContains(response, other_profile.line_id)
        self.assertNotContains(response, self.password)
        self.assertNotContains(response, self.user.password)

    def test_zero_coordinates_are_displayed_as_a_saved_location(self):
        self.profile.default_latitude = Decimal("0")
        self.profile.default_longitude = Decimal("0")
        self.profile.save()
        self.client.force_login(self.user)

        response = self.client.get(self.profile_url)

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Belum diisi")
        self.assertEqual(response.context["profile"].default_latitude, Decimal("0"))
        self.assertEqual(response.context["profile"].default_longitude, Decimal("0"))

    def test_user_controlled_contact_is_escaped_in_html(self):
        malicious_line = '<script>alert("kontak")</script>'
        self.profile.line_id = malicious_line
        self.profile.save()
        self.client.force_login(self.user)

        response = self.client.get(self.profile_url)

        self.assertContains(response, escape(malicious_line))
        self.assertNotContains(response, malicious_line)

    def test_account_without_profile_shows_empty_data_without_creating_records(self):
        # Akun lama atau akun admin bisa dibuat tanpa melalui form registrasi.
        self.profile.delete()
        self.client.force_login(self.user)

        response = self.client.get(self.profile_url)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["profile"])
        self.assertContains(response, "Belum diisi")
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(UserProfile.objects.count(), 0)

    def test_private_profile_is_not_stored_in_browser_or_shared_caches(self):
        self.client.force_login(self.user)

        response = self.client.get(self.profile_url)

        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("private", response["Cache-Control"])

    def test_profile_is_read_only_and_does_not_accept_write_methods(self):
        self.client.force_login(self.user)

        for method in ("POST", "PUT", "PATCH", "DELETE"):
            with self.subTest(method=method):
                response = self.client.generic(method, self.profile_url)

                self.assertEqual(response.status_code, 405)

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.whatsapp_number, "6281234567890")
        self.assertEqual(UserProfile.objects.count(), 1)


class LogoutTests(AccountTestCase):
    def test_get_cannot_log_a_user_out(self):
        self.client.force_login(self.user)

        response = self.client.get(self.logout_url)

        self.assertEqual(response.status_code, 405)
        self.assertEqual(self.client.session["_auth_user_id"], str(self.user.pk))

    def test_post_logs_out_and_protected_profile_requires_login_again(self):
        self.client.force_login(self.user)

        response = self.client.post(self.logout_url)

        self.assertRedirects(response, reverse("landing_page"))
        self.assertNotIn("_auth_user_id", self.client.session)
        protected_response = self.client.get(self.profile_url)
        self.assertEqual(protected_response.status_code, 302)
        self.assertEqual(urlsplit(protected_response["Location"]).path, self.login_url)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())
        self.assertTrue(UserProfile.objects.filter(pk=self.profile.pk).exists())

    def test_logout_ignores_next_and_always_returns_to_landing_page(self):
        # Tujuan logout tetap beranda, termasuk jika next menunjuk logout sendiri.
        for destination in (
            self.logout_url,
            self.profile_url,
            "https://evil.example/",
        ):
            for source in ("post", "query"):
                with self.subTest(destination=destination, source=source):
                    client = Client()
                    client.force_login(self.user)
                    if source == "post":
                        response = client.post(self.logout_url, {"next": destination})
                    else:
                        response = client.post(
                            self.logout_url, query_params={"next": destination}
                        )

                    self.assertRedirects(response, reverse("landing_page"))
                    self.assertNotIn("_auth_user_id", client.session)

    def test_logout_requires_valid_csrf_token_and_preserves_session_if_rejected(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.get(self.profile_url)
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        token = client.cookies["csrftoken"].value

        for payload in ({}, {"csrfmiddlewaretoken": "token-tidak-valid"}):
            with self.subTest(payload=payload):
                response = client.post(self.logout_url, payload)

                self.assertEqual(response.status_code, 403)
                self.assertEqual(client.session["_auth_user_id"], str(self.user.pk))

        response = client.post(self.logout_url, {"csrfmiddlewaretoken": token})

        self.assertRedirects(response, reverse("landing_page"))
        self.assertNotIn("_auth_user_id", client.session)

    def test_navigation_switches_between_guest_links_and_authenticated_actions(self):
        guest_response = self.client.get(reverse("landing_page"))
        self.assertContains(guest_response, f'href="{self.login_url}"')
        self.assertContains(
            guest_response, f'href="{reverse("userprofile:register")}"'
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("landing_page"))

        self.assertContains(response, f'href="{self.profile_url}"')
        self.assertContains(response, f'action="{self.logout_url}"')
        self.assertContains(response, 'method="post"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertNotContains(response, f'href="{self.login_url}"')
        self.assertNotContains(response, f'href="{reverse("userprofile:register")}"')