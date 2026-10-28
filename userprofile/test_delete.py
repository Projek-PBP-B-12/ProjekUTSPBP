"""Tes tahap 4: hapus akun sendiri dengan konfirmasi dan transaksi database.

Semua penghapusan memakai database tes sementara, bukan database aplikasi.
"""

from decimal import Decimal
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model, login
from django.contrib.auth.hashers import PBKDF2PasswordHasher
from django.contrib.messages import SUCCESS, get_messages
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.db import IntegrityError
from django.db.models.deletion import ProtectedError, RestrictedError
from django.db.models.signals import post_delete
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from Location.models import Location
from userprofile.models import UserProfile


User = get_user_model()


class DeleteAccountTests(TestCase):
    password = "J9!mango-leaf-river"
    other_password = "R8!another-safe-account"

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            username="akun_yang_dihapus", password=cls.password
        )
        cls.profile = UserProfile.objects.create(
            user=cls.owner,
            whatsapp_number="6281234567890",
            line_id="pemilik.line",
            default_location=Location.objects.create(owner=cls.owner, area_name="Rumah",
                latitude=Decimal("-6.360000"), longitude=Decimal("106.820000")),
        )
        cls.other = User.objects.create_user(
            username="akun_tetap_ada", password=cls.other_password
        )
        cls.other_profile = UserProfile.objects.create(
            user=cls.other, line_id="tetangga.line"
        )

    def setUp(self):
        self.delete_url = reverse("userprofile:delete_account")
        self.profile_url = reverse("userprofile:profile")
        self.payload = {"password": self.password, "confirm": "on"}

    def assert_owner_preserved(self, client=None):
        self.owner.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.user_id, self.owner.pk)
        self.assertEqual(self.profile.whatsapp_number, "6281234567890")
        self.assertEqual(self.profile.line_id, "pemilik.line")
        self.assertEqual(self.profile.default_location.latitude, Decimal("-6.360000"))
        self.assertEqual(self.profile.default_location.longitude, Decimal("106.820000"))
        self.assertTrue(self.owner.check_password(self.password))
        if client is not None:
            self.assertEqual(client.session["_auth_user_id"], str(self.owner.pk))

    def assert_other_preserved(self):
        self.other.refresh_from_db()
        self.other_profile.refresh_from_db()
        self.assertEqual(self.other.username, "akun_tetap_ada")
        self.assertTrue(self.other.check_password(self.other_password))
        self.assertEqual(self.other_profile.line_id, "tetangga.line")

    def test_anonymous_get_and_post_require_login_without_deleting_accounts(self):
        for method in ("get", "post"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(self.delete_url, self.payload)

                self.assertEqual(response.status_code, 302)
                destination = urlsplit(response["Location"])
                self.assertEqual(destination.path, reverse("userprofile:login"))
                self.assertEqual(
                    urlsplit(parse_qs(destination.query)["next"][0]).path,
                    self.delete_url,
                )
                self.assertEqual(User.objects.count(), 2)
                self.assertEqual(UserProfile.objects.count(), 2)
                self.assertIn("no-store", response["Cache-Control"])

    def test_confirmation_page_requires_password_and_unchecked_confirmation(self):
        self.client.force_login(self.owner)

        response = self.client.get(self.delete_url)

        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertEqual(set(form.fields), {"password", "confirm"})
        self.assertTrue(form.fields["password"].required)
        self.assertTrue(form.fields["confirm"].required)
        self.assertFalse(form["confirm"].value())
        self.assertContains(response, 'type="password"')
        self.assertContains(response, 'autocomplete="current-password"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertContains(response, self.owner.username)
        self.assertNotContains(response, self.password)
        self.assertNotContains(response, self.owner.password)
        self.assert_owner_preserved(self.client)

    def test_get_with_valid_credentials_in_query_never_deletes_account(self):
        self.client.force_login(self.owner)

        response = self.client.get(self.delete_url, self.payload)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["form"].is_bound)
        self.assert_owner_preserved(self.client)

    def test_head_is_read_only(self):
        self.client.force_login(self.owner)

        response = self.client.head(self.delete_url)

        self.assertEqual(response.status_code, 200)
        self.assert_owner_preserved(self.client)

    def test_missing_or_wrong_password_does_not_delete_and_is_not_echoed(self):
        self.client.force_login(self.owner)
        for password in ("", "kata-sandi-yang-salah", self.other_password):
            with self.subTest(password=password):
                response = self.client.post(
                    self.delete_url, self.payload | {"password": password}
                )

                self.assertEqual(response.status_code, 200)
                self.assertIn("password", response.context["form"].errors)
                if password:
                    self.assertNotContains(response, password)
                self.assert_owner_preserved(self.client)

    def test_correct_password_without_confirmation_does_not_delete(self):
        self.client.force_login(self.owner)

        response = self.client.post(self.delete_url, {"password": self.password})

        self.assertEqual(response.status_code, 200)
        self.assertIn("confirm", response.context["form"].errors)
        self.assertNotContains(response, self.password)
        self.assert_owner_preserved(self.client)

    def test_missing_confirmation_does_not_upgrade_legacy_hash_or_break_session(self):
        # Hash lama sengaja dibuat murah agar Django mendeteksi perlu upgrade.
        legacy_hash = PBKDF2PasswordHasher().encode(
            self.password, salt="garam-regresi-akun", iterations=1
        )
        self.owner.password = legacy_hash
        self.owner.save(update_fields=["password"])
        self.client.force_login(self.owner)
        profile_before = UserProfile.objects.filter(pk=self.profile.pk).values().get()

        response = self.client.post(self.delete_url, {"password": self.password})

        self.assertEqual(response.status_code, 200)
        self.assertIn("confirm", response.context["form"].errors)
        self.assertNotContains(response, self.password)
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.password, legacy_hash)
        self.assertEqual(
            UserProfile.objects.filter(pk=self.profile.pk).values().get(),
            profile_before,
        )
        self.assertEqual(self.client.session["_auth_user_id"], str(self.owner.pk))
        next_response = self.client.get(self.profile_url)
        self.assertEqual(next_response.status_code, 200)
        self.assertTrue(next_response.wsgi_request.user.is_authenticated)
        self.assertEqual(next_response.wsgi_request.user.pk, self.owner.pk)

    def test_empty_post_is_invalid_and_keeps_session(self):
        self.client.force_login(self.owner)

        response = self.client.post(self.delete_url, {})

        self.assertEqual(response.status_code, 200)
        self.assertIn("password", response.context["form"].errors)
        self.assertIn("confirm", response.context["form"].errors)
        self.assert_owner_preserved(self.client)

    def test_confirmed_deletion_removes_account_profile_and_session(self):
        self.client.force_login(self.owner)

        response = self.client.post(self.delete_url, self.payload)

        self.assertRedirects(response, reverse("landing_page"))
        self.assertFalse(User.objects.filter(pk=self.owner.pk).exists())
        self.assertFalse(UserProfile.objects.filter(pk=self.profile.pk).exists())
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertTrue(
            any(message.level == SUCCESS for message in get_messages(response.wsgi_request))
        )
        self.assert_other_preserved()

    def test_injected_target_ids_still_delete_only_the_session_owner(self):
        self.client.force_login(self.owner)
        payload = self.payload | {
            "user": self.other.pk,
            "user_id": self.other.pk,
            "id": self.other.pk,
            "pk": self.other.pk,
            "profile_id": self.other_profile.pk,
            "username": self.other.username,
            "next": "https://evil.example/",
        }

        response = self.client.post(
            self.delete_url, payload, query_params={"user_id": self.other.pk}
        )

        self.assertRedirects(response, reverse("landing_page"))
        self.assertFalse(User.objects.filter(pk=self.owner.pk).exists())
        self.assertFalse(UserProfile.objects.filter(pk=self.profile.pk).exists())
        self.assert_other_preserved()

    def test_staff_account_cannot_use_this_route_to_delete_someone_else(self):
        self.owner.is_staff = True
        self.owner.is_superuser = True
        self.owner.save(update_fields=["is_staff", "is_superuser"])
        self.client.force_login(self.owner)

        response = self.client.post(
            self.delete_url, self.payload | {"user_id": self.other.pk}
        )

        self.assertRedirects(response, reverse("landing_page"))
        self.assertFalse(User.objects.filter(pk=self.owner.pk).exists())
        self.assert_other_preserved()

    def test_legacy_account_without_profile_can_be_deleted(self):
        self.profile.delete()
        self.client.force_login(self.owner)

        response = self.client.post(self.delete_url, self.payload)

        self.assertRedirects(response, reverse("landing_page"))
        self.assertFalse(User.objects.filter(pk=self.owner.pk).exists())
        self.assertEqual(UserProfile.objects.count(), 1)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_unusable_password_cannot_confirm_deletion(self):
        self.owner.set_unusable_password()
        self.owner.save(update_fields=["password"])
        self.client.force_login(self.owner)

        response = self.client.post(self.delete_url, self.payload)

        self.assertEqual(response.status_code, 200)
        self.assertIn("password", response.context["form"].errors)
        self.assertTrue(User.objects.filter(pk=self.owner.pk).exists())
        self.assertTrue(UserProfile.objects.filter(pk=self.profile.pk).exists())
        self.assertEqual(self.client.session["_auth_user_id"], str(self.owner.pk))

    def test_password_spaces_are_not_stripped_during_verification(self):
        spaced_password = "  P4!exact-password-spaces  "
        self.owner.set_password(spaced_password)
        self.owner.save(update_fields=["password"])
        self.client.force_login(self.owner)

        response = self.client.post(
            self.delete_url, self.payload | {"password": spaced_password}
        )

        self.assertRedirects(response, reverse("landing_page"))
        self.assertFalse(User.objects.filter(pk=self.owner.pk).exists())

    def test_csrf_missing_or_invalid_cannot_delete_but_valid_token_can(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        client.get(self.delete_url)
        token = client.cookies["csrftoken"].value

        for extra in ({}, {"csrfmiddlewaretoken": "token-tidak-valid"}):
            with self.subTest(extra=extra):
                response = client.post(self.delete_url, self.payload | extra)

                self.assertEqual(response.status_code, 403)
                self.assert_owner_preserved(client)

        response = client.post(
            self.delete_url, self.payload | {"csrfmiddlewaretoken": token}
        )

        self.assertRedirects(response, reverse("landing_page"))
        self.assertFalse(User.objects.filter(pk=self.owner.pk).exists())
        self.assertNotIn("_auth_user_id", client.session)

    def test_unsupported_methods_cannot_delete_account(self):
        self.client.force_login(self.owner)
        for method in ("PUT", "PATCH", "DELETE"):
            with self.subTest(method=method):
                response = self.client.generic(method, self.delete_url)

                self.assertEqual(response.status_code, 405)
                self.assert_owner_preserved(self.client)

    def test_second_session_loses_protected_access_after_account_is_deleted(self):
        self.client.force_login(self.owner)
        second_client = Client()
        second_client.force_login(self.owner)

        self.client.post(self.delete_url, self.payload)
        response = second_client.get(self.profile_url)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(urlsplit(response["Location"]).path, reverse("userprofile:login"))
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_deleted_account_cannot_login_again(self):
        self.client.force_login(self.owner)
        self.client.post(self.delete_url, self.payload)

        response = self.client.post(
            reverse("userprofile:login"),
            {"username": self.owner.username, "password": self.password},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_deleted_contact_is_not_available_to_other_logged_in_user(self):
        self.client.force_login(self.owner)
        other_client = Client()
        other_client.force_login(self.other)
        contact_url = reverse(
            "userprofile:donor_contact", kwargs={"user_id": self.owner.pk}
        )
        self.client.post(self.delete_url, self.payload)

        response = other_client.get(contact_url)

        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, self.profile.whatsapp_number, status_code=404)

    def test_protected_or_restricted_relations_keep_account_and_show_friendly_error(self):
        self.client.force_login(self.owner)
        for error_class in (ProtectedError, RestrictedError):
            with self.subTest(error_class=error_class.__name__):
                error = error_class("detail-relasi-internal-rahasia", {self.profile})
                with patch.object(User, "delete", side_effect=error):
                    response = self.client.post(self.delete_url, self.payload)

                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].non_field_errors())
                self.assertNotContains(response, "detail-relasi-internal-rahasia")
                self.assertNotContains(response, self.password)
                self.assert_owner_preserved(self.client)
                self.assert_other_preserved()

    def test_database_failure_rolls_back_profile_deletion_and_keeps_login(self):
        self.client.force_login(self.owner)

        def fail_after_profile_delete(sender, instance, **kwargs):
            if instance.pk == self.profile.pk:
                raise IntegrityError("simulasi-gagal-setelah-profil-dihapus")

        post_delete.connect(fail_after_profile_delete, sender=UserProfile, weak=False)
        try:
            with self.assertRaises(IntegrityError):
                self.client.post(self.delete_url, self.payload)
        finally:
            post_delete.disconnect(fail_after_profile_delete, sender=UserProfile)

        self.assert_owner_preserved(self.client)
        self.assert_other_preserved()

    def test_current_database_password_is_used_even_if_request_user_is_stale(self):
        from userprofile.views import delete_account

        # Simulasikan perubahan password setelah middleware memuat request.user.
        request = RequestFactory().post(self.delete_url, self.payload)
        request.user = self.owner
        SessionMiddleware(lambda request: None).process_request(request)
        MessageMiddleware(lambda request: None).process_request(request)
        login(request, self.owner, backend="django.contrib.auth.backends.ModelBackend")
        current_owner = User.objects.get(pk=self.owner.pk)
        current_owner.set_password("M8!password-baru-di-database")
        current_owner.save(update_fields=["password"])

        response = delete_account(request)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(pk=self.owner.pk).exists())
        self.assertTrue(UserProfile.objects.filter(pk=self.profile.pk).exists())
        self.assertNotContains(response, self.password)

    def test_confirmation_errors_and_success_responses_are_not_cached(self):
        self.client.force_login(self.owner)
        responses = (
            self.client.get(self.delete_url),
            self.client.post(self.delete_url, {"password": self.password}),
            self.client.post(self.delete_url, self.payload),
        )

        for response in responses:
            with self.subTest(status=response.status_code):
                self.assertIn("no-store", response["Cache-Control"])
                self.assertIn("private", response["Cache-Control"])

    def test_profile_links_to_confirmation_page(self):
        self.client.force_login(self.owner)

        response = self.client.get(self.profile_url)

        self.assertContains(response, f'href="{self.delete_url}"')
