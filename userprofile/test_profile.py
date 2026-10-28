"""Tes tahap 3: mengubah profil sendiri dan membaca kontak pengguna lain."""

from decimal import Decimal
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model
from django.contrib.messages import SUCCESS, get_messages
from django.test import Client, TestCase
from django.urls import reverse
from django.utils.html import escape

from Location.models import Location
from userprofile.models import UserProfile


User = get_user_model()


class ProfileTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="pemilik_profil", email="pemilik@example.com")
        cls.profile = UserProfile.objects.create(
            user=cls.owner,
            whatsapp_number="6281234567890",
            line_id="pemilik.line",
            default_location=Location.objects.create(owner=cls.owner, area_name="Rumah",
                latitude=Decimal("-6.360000"), longitude=Decimal("106.820000")),
        )
        cls.other = User.objects.create_user(
            username="donor_lain", email="email-pribadi@example.com"
        )
        cls.other_profile = UserProfile.objects.create(
            user=cls.other,
            whatsapp_number="6289876543210",
            line_id="donor.line",
            default_location=Location.objects.create(owner=cls.other, area_name="Rumah donor",
                latitude=Decimal("-7.123456"), longitude=Decimal("107.654321")),
        )

    def setUp(self):
        self.edit_url = reverse("userprofile:profile_edit")
        self.profile_url = reverse("userprofile:profile")
        self.contact_url = reverse(
            "userprofile:donor_contact", kwargs={"user_id": self.other.pk}
        )
        self.campus = Location.objects.create(owner=self.owner, area_name="Kampus", latitude=-6.2, longitude=106.8)
        self.payload = {
            "whatsapp_number": "6281122233344",
            "line_id": "kontak.baru",
            "default_location": self.campus.pk,
            "email": "email-baru@example.com",
        }
        self.initial_values = self.profile_values(self.profile)

    @staticmethod
    def profile_values(profile):
        return (
            profile.user_id,
            profile.whatsapp_number,
            profile.line_id,
            profile.default_location_id,
        )

    def assert_profile_unchanged(self):
        self.profile.refresh_from_db()
        self.assertEqual(self.profile_values(self.profile), self.initial_values)


class ProfileEditTests(ProfileTestCase):
    def test_anonymous_get_and_post_require_login_without_changing_profile(self):
        for method in ("get", "post"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(self.edit_url, self.payload)

                self.assertEqual(response.status_code, 302)
                destination = urlsplit(response["Location"])
                self.assertEqual(destination.path, reverse("userprofile:login"))
                self.assertEqual(
                    urlsplit(parse_qs(destination.query)["next"][0]).path,
                    self.edit_url,
                )
                self.assert_profile_unchanged()

    def test_form_loads_saved_values_and_only_exposes_editable_profile_fields(self):
        self.client.force_login(self.owner)

        response = self.client.get(self.edit_url)

        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertEqual(set(form.fields), set(self.payload))
        self.assertFalse(form.is_bound)
        self.assertEqual(form.initial["whatsapp_number"], self.profile.whatsapp_number)
        self.assertEqual(form.initial["line_id"], self.profile.line_id)
        self.assertEqual(form.initial["default_location"], self.profile.default_location_id)
        self.assertEqual(form.initial["email"], self.owner.email)
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assert_profile_unchanged()

    def test_valid_post_updates_existing_profile_and_redirects_with_success(self):
        self.client.force_login(self.owner)
        original_pk = self.profile.pk

        response = self.client.post(self.edit_url, self.payload)

        self.assertRedirects(response, self.profile_url)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.pk, original_pk)
        self.assertEqual(self.profile.user_id, self.owner.pk)
        self.assertEqual(self.profile.whatsapp_number, self.payload["whatsapp_number"])
        self.assertEqual(self.profile.line_id, self.payload["line_id"])
        self.assertEqual(self.profile.default_location, self.campus)
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.email, self.payload["email"])
        self.assertEqual(UserProfile.objects.count(), 2)
        self.assertTrue(
            any(message.level == SUCCESS for message in get_messages(response.wsgi_request))
        )
        detail = self.client.get(self.profile_url)
        self.assertContains(detail, self.payload["whatsapp_number"])
        self.assertContains(detail, self.payload["line_id"])

    def test_injected_owner_and_account_fields_cannot_modify_another_account(self):
        self.client.force_login(self.owner)
        other_values = self.profile_values(self.other_profile)
        payload = self.payload | {
            "user": self.other.pk,
            "user_id": self.other.pk,
            "id": self.other_profile.pk,
            "pk": self.other_profile.pk,
            "username": "mengambil_identitas",
            "password": "mengganti-password",
            "is_superuser": "true",
            "is_staff": "true",
        }

        response = self.client.post(
            self.edit_url, payload, query_params={"user_id": self.other.pk}
        )

        self.assertRedirects(response, self.profile_url)
        self.profile.refresh_from_db()
        self.other_profile.refresh_from_db()
        self.owner.refresh_from_db()
        self.assertEqual(self.profile.user_id, self.owner.pk)
        self.assertEqual(self.profile.line_id, self.payload["line_id"])
        self.assertEqual(self.profile_values(self.other_profile), other_values)
        self.assertEqual(self.owner.username, "pemilik_profil")
        self.assertFalse(self.owner.has_usable_password())
        self.assertFalse(self.owner.is_staff)
        self.assertFalse(self.owner.is_superuser)
        self.assertEqual(UserProfile.objects.count(), 2)

    def test_optional_contacts_and_default_location_can_be_cleared(self):
        self.client.force_login(self.owner)

        response = self.client.post(self.edit_url, dict.fromkeys(self.payload, "") | {"email": self.payload["email"]})

        self.assertRedirects(response, self.profile_url)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.whatsapp_number, "")
        self.assertEqual(self.profile.line_id, "")
        self.assertIsNone(self.profile.default_location)
        self.assertTrue(Location.objects.filter(pk=self.campus.pk).exists())

    def test_form_choices_include_only_owned_locations(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.edit_url)
        choices = response.context["form"].fields["default_location"].queryset
        self.assertEqual(set(choices.values_list("pk", flat=True)), {self.profile.default_location_id, self.campus.pk})
        self.assertNotContains(response, "Rumah donor")

    def test_invalid_whatsapp_numbers_reject_the_entire_update(self):
        self.client.force_login(self.owner)
        for number in (
            "08123456789",
            "+628123456789",
            "62812 3456789",
            "1234567",
            "1234567890123456",
            "62812345678a",
            "٦٢٨١٢٣٤٥٦٧٨٩",
        ):
            with self.subTest(number=number):
                response = self.client.post(
                    self.edit_url, self.payload | {"whatsapp_number": number}
                )

                self.assertEqual(response.status_code, 200)
                self.assertIn("whatsapp_number", response.context["form"].errors)
                self.assert_profile_unchanged()

    def test_too_long_line_id_is_rejected_without_saving_other_fields(self):
        self.client.force_login(self.owner)

        response = self.client.post(self.edit_url, self.payload | {"line_id": "a" * 101})

        self.assertEqual(response.status_code, 200)
        self.assertIn("line_id", response.context["form"].errors)
        self.assert_profile_unchanged()

    def test_another_users_location_is_rejected_without_saving_email_or_contacts(self):
        self.client.force_login(self.owner)
        response = self.client.post(self.edit_url, self.payload | {"default_location": self.other_profile.default_location_id})
        self.assertEqual(response.status_code, 200)
        self.assertIn("default_location", response.context["form"].errors)
        self.assert_profile_unchanged()
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.email, "pemilik@example.com")

    def test_missing_or_invalid_location_id_is_rejected_without_database_changes(self):
        self.client.force_login(self.owner)
        for value in ("bukan-angka", "999999999"):
            with self.subTest(value=value):
                response = self.client.post(self.edit_url, self.payload | {"default_location": value})
                self.assertEqual(response.status_code, 200)
                self.assertIn("default_location", response.context["form"].errors)
                self.assert_profile_unchanged()

    def test_get_for_legacy_account_does_not_create_a_profile(self):
        self.profile.delete()
        self.client.force_login(self.owner)

        response = self.client.get(self.edit_url)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["form"].is_bound)
        self.assertFalse(UserProfile.objects.filter(user=self.owner).exists())

    def test_invalid_post_for_legacy_account_does_not_create_a_profile(self):
        self.profile.delete()
        self.client.force_login(self.owner)

        response = self.client.post(
            self.edit_url, self.payload | {"email": ""}
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertFalse(UserProfile.objects.filter(user=self.owner).exists())

    def test_valid_post_for_legacy_account_creates_exactly_one_profile(self):
        self.profile.delete()
        self.client.force_login(self.owner)

        for _ in range(2):
            response = self.client.post(self.edit_url, self.payload)

            self.assertRedirects(response, self.profile_url)
            self.assertEqual(UserProfile.objects.filter(user=self.owner).count(), 1)
            profile = UserProfile.objects.get(user=self.owner)
            self.assertEqual(profile.whatsapp_number, self.payload["whatsapp_number"])
            self.assertEqual(profile.line_id, self.payload["line_id"])
        self.assertEqual(UserProfile.objects.count(), 2)

    def test_update_requires_valid_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        client.get(self.edit_url)
        token = client.cookies["csrftoken"].value

        for extra in ({}, {"csrfmiddlewaretoken": "token-tidak-valid"}):
            with self.subTest(extra=extra):
                response = client.post(self.edit_url, self.payload | extra)

                self.assertEqual(response.status_code, 403)
                self.assert_profile_unchanged()

        response = client.post(
            self.edit_url, self.payload | {"csrfmiddlewaretoken": token}
        )
        self.assertRedirects(response, self.profile_url)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.line_id, self.payload["line_id"])

    def test_unsupported_methods_cannot_update_profile(self):
        self.client.force_login(self.owner)
        for method in ("PUT", "PATCH", "DELETE"):
            with self.subTest(method=method):
                response = self.client.generic(method, self.edit_url)

                self.assertEqual(response.status_code, 405)
                self.assert_profile_unchanged()

    def test_edit_responses_are_not_stored_in_caches(self):
        self.client.force_login(self.owner)
        for response in (
            self.client.get(self.edit_url),
            self.client.post(self.edit_url, self.payload | {"line_id": "a" * 101}),
            self.client.post(self.edit_url, self.payload),
        ):
            with self.subTest(status=response.status_code):
                self.assertIn("no-store", response["Cache-Control"])
                self.assertIn("private", response["Cache-Control"])

    def test_own_profile_links_to_edit_form(self):
        self.client.force_login(self.owner)

        response = self.client.get(self.profile_url)

        self.assertContains(response, f'href="{self.edit_url}"')


class DonorContactTests(ProfileTestCase):
    def test_anonymous_user_cannot_read_contacts(self):
        response = self.client.get(self.contact_url)

        self.assertEqual(response.status_code, 302)
        destination = urlsplit(response["Location"])
        self.assertEqual(destination.path, reverse("userprofile:login"))
        self.assertEqual(parse_qs(destination.query)["next"], [self.contact_url])
        self.assertNotContains(response, self.other_profile.whatsapp_number, status_code=302)
        self.assertIn("no-store", response["Cache-Control"])

    def test_authenticated_user_sees_only_target_contact_and_no_private_profile_data(self):
        self.client.force_login(self.owner)

        response = self.client.get(self.contact_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.other.username)
        self.assertContains(response, self.other_profile.whatsapp_number)
        self.assertContains(response, self.other_profile.line_id)
        self.assertContains(
            response, f'href="https://wa.me/{self.other_profile.whatsapp_number}"'
        )
        for private_value in (
            self.other.email,
            self.other.password,
            str(self.other_profile.default_location.latitude),
            str(self.other_profile.default_location.longitude),
            "-7,123456",
            "107,654321",
            self.profile.whatsapp_number,
            self.profile.line_id,
        ):
            with self.subTest(private_value=private_value):
                self.assertNotContains(response, private_value)
        self.assertEqual(UserProfile.objects.count(), 2)

    def test_account_without_profile_shows_empty_contact_without_creating_profile(self):
        self.other_profile.delete()
        self.client.force_login(self.owner)

        response = self.client.get(self.contact_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.other.username)
        self.assertContains(response, "Belum diisi")
        self.assertNotContains(response, "https://wa.me/")
        self.assertFalse(UserProfile.objects.filter(user=self.other).exists())

    def test_empty_contacts_have_no_whatsapp_link(self):
        UserProfile.objects.filter(pk=self.other_profile.pk).update(
            whatsapp_number="", line_id=""
        )
        self.client.force_login(self.owner)

        response = self.client.get(self.contact_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Belum diisi")
        self.assertNotContains(response, "https://wa.me/")

    def test_missing_or_inactive_account_returns_not_found(self):
        self.client.force_login(self.owner)
        missing_url = reverse(
            "userprofile:donor_contact", kwargs={"user_id": self.other.pk + 1000}
        )
        User.objects.filter(pk=self.other.pk).update(is_active=False)

        for url in (missing_url, self.contact_url):
            with self.subTest(url=url):
                response = self.client.get(url)

                self.assertEqual(response.status_code, 404)
                self.assertNotContains(
                    response, self.other_profile.whatsapp_number, status_code=404
                )

    def test_line_id_is_escaped_and_is_not_used_as_an_arbitrary_link(self):
        malicious_line = '<script>alert("kontak")</script>'
        UserProfile.objects.filter(pk=self.other_profile.pk).update(line_id=malicious_line)
        self.client.force_login(self.owner)

        response = self.client.get(self.contact_url)

        self.assertContains(response, escape(malicious_line))
        self.assertNotContains(response, malicious_line)
        self.assertNotContains(response, 'href="javascript:')

    def test_invalid_legacy_whatsapp_value_is_not_used_to_build_a_link(self):
        self.client.force_login(self.owner)
        for number in ("javascript:x", "//evil.test", "08123456789", "٦٢٨١٢٣٤٥٦٧٨٩"):
            with self.subTest(number=number):
                # ORM update bisa melewati validator; keluaran tetap harus aman.
                UserProfile.objects.filter(pk=self.other_profile.pk).update(
                    whatsapp_number=number
                )

                response = self.client.get(self.contact_url)

                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, "https://wa.me/")
                self.assertNotContains(response, 'href="javascript:')
                self.assertNotContains(response, 'href="//evil.test')

    def test_contact_endpoint_rejects_write_methods_and_preserves_target_profile(self):
        self.client.force_login(self.owner)
        original = self.profile_values(self.other_profile)
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            with self.subTest(method=method):
                response = self.client.generic(method, self.contact_url)

                self.assertEqual(response.status_code, 405)
                self.other_profile.refresh_from_db()
                self.assertEqual(self.profile_values(self.other_profile), original)

    def test_contact_page_has_private_no_store_headers(self):
        self.client.force_login(self.owner)

        response = self.client.get(self.contact_url)

        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("private", response["Cache-Control"])

    def test_saved_contact_changes_and_removal_are_reflected_for_other_users(self):
        self.client.force_login(self.other)
        response = self.client.post(self.edit_url, self.payload | {"default_location": ""})
        self.assertRedirects(response, self.profile_url)

        self.client.force_login(self.owner)
        response = self.client.get(self.contact_url)
        self.assertContains(response, self.payload["whatsapp_number"])
        self.assertContains(response, self.payload["line_id"])
        self.assertNotContains(response, self.other_profile.whatsapp_number)

        self.client.force_login(self.other)
        self.client.post(self.edit_url, dict.fromkeys(self.payload, "") | {"email": self.payload["email"]})
        self.client.force_login(self.owner)
        response = self.client.get(self.contact_url)
        self.assertContains(response, "Belum diisi")
        self.assertNotContains(response, self.payload["whatsapp_number"])
        self.assertNotContains(response, self.payload["line_id"])
