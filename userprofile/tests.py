from decimal import Decimal
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import authenticate, get_user_model
from django.contrib.messages import SUCCESS, get_messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from .forms import RegistrationForm
from .models import UserProfile
from .admin import UserProfileAdmin


User = get_user_model()


class UserProfileModelTests(TestCase):
    """Memeriksa data profil dan aturan yang dijaga oleh database."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="pemilik_profil")

    def test_contact_and_location_can_be_empty(self):
        profile = UserProfile(user=self.user)

        profile.full_clean()
        profile.save()
        profile.refresh_from_db()

        self.assertEqual(profile.whatsapp_number, "")
        self.assertEqual(profile.line_id, "")
        self.assertIsNone(profile.default_latitude)
        self.assertIsNone(profile.default_longitude)
        self.assertEqual(self.user.profile.pk, profile.pk)

    def test_user_cannot_have_two_profiles(self):
        UserProfile.objects.create(user=self.user)

        # Savepoint menjaga koneksi tes tetap bisa dipakai setelah error SQL.
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                UserProfile.objects.create(user=self.user)

        self.assertEqual(UserProfile.objects.filter(user=self.user).count(), 1)

    def test_deleting_user_also_deletes_profile(self):
        profile = UserProfile.objects.create(user=self.user)
        profile_id = profile.pk

        self.user.delete()

        self.assertFalse(UserProfile.objects.filter(pk=profile_id).exists())

    def test_whatsapp_accepts_supported_format_and_empty_value(self):
        for number in ("", "12345678", "6281234567890", "123456789012345"):
            with self.subTest(number=number):
                profile = UserProfile(user=self.user, whatsapp_number=number)
                profile.full_clean()

    def test_whatsapp_rejects_invalid_format(self):
        for number in (
            "08123456789",       # Diawali nol, bukan kode negara.
            "+628123456789",     # Tanda + tidak disimpan dalam model ini.
            "62812 3456789",     # Mengandung spasi.
            "62812345678a",      # Mengandung huruf.
            "1234567",          # Terlalu pendek.
            "1234567890123456", # Terlalu panjang.
            "٦٢٨١٢٣٤٥٦٧٨٩",      # Bukan digit ASCII 0 sampai 9.
        ):
            with self.subTest(number=number):
                profile = UserProfile(user=self.user, whatsapp_number=number)
                with self.assertRaises(ValidationError) as error:
                    profile.full_clean()
                self.assertIn("whatsapp_number", error.exception.message_dict)

    def test_line_id_has_a_maximum_length(self):
        UserProfile(user=self.user, line_id="a" * 100).full_clean()

        with self.assertRaises(ValidationError) as error:
            UserProfile(user=self.user, line_id="a" * 101).full_clean()

        self.assertIn("line_id", error.exception.message_dict)

    def test_coordinates_accept_zero_and_valid_boundaries(self):
        profile = UserProfile.objects.create(user=self.user)

        for latitude, longitude in (
            ("0", "0"),
            ("-90", "-180"),
            ("90", "180"),
            ("-6.360000", "106.820000"),
        ):
            with self.subTest(latitude=latitude, longitude=longitude):
                profile.default_latitude = Decimal(latitude)
                profile.default_longitude = Decimal(longitude)
                profile.full_clean()
                profile.save()
                profile.refresh_from_db()

                self.assertEqual(profile.default_latitude, Decimal(latitude))
                self.assertEqual(profile.default_longitude, Decimal(longitude))

    def test_model_rejects_incomplete_or_out_of_range_coordinates(self):
        cases = (
            (Decimal("1"), None),
            (None, Decimal("1")),
            (Decimal("-90.000001"), Decimal("0")),
            (Decimal("90.000001"), Decimal("0")),
            (Decimal("0"), Decimal("-180.000001")),
            (Decimal("0"), Decimal("180.000001")),
        )
        for latitude, longitude in cases:
            with self.subTest(latitude=latitude, longitude=longitude):
                profile = UserProfile(
                    user=self.user,
                    default_latitude=latitude,
                    default_longitude=longitude,
                )
                with self.assertRaises(ValidationError):
                    profile.full_clean()

    def test_database_rejects_bad_coordinates_without_full_clean(self):
        profile = UserProfile.objects.create(user=self.user)
        cases = (
            (Decimal("1"), None),
            (None, Decimal("1")),
            (Decimal("-91"), Decimal("0")),
            (Decimal("91"), Decimal("0")),
            (Decimal("0"), Decimal("-181")),
            (Decimal("0"), Decimal("181")),
        )
        for latitude, longitude in cases:
            with self.subTest(latitude=latitude, longitude=longitude):
                # update() melewati validasi model; constraint DB tetap berlaku.
                with self.assertRaises(IntegrityError):
                    with transaction.atomic():
                        UserProfile.objects.filter(pk=profile.pk).update(
                            default_latitude=latitude,
                            default_longitude=longitude,
                        )

                profile.refresh_from_db()
                self.assertIsNone(profile.default_latitude)
                self.assertIsNone(profile.default_longitude)


class RegistrationFormTests(TestCase):
    """Validasi form dapat diuji tanpa template HTML atau browser."""

    def setUp(self):
        self.data = {
            "username": "pengguna_baru",
            "password1": "Q7!mango-river-planet",
            "password2": "Q7!mango-river-planet",
        }

    def test_valid_form_saves_a_hashed_and_usable_password(self):
        form = RegistrationForm(data=self.data)
        self.assertTrue(form.is_valid(), form.errors)

        user = form.save()
        user.refresh_from_db()

        self.assertNotEqual(user.password, self.data["password1"])
        self.assertTrue(user.check_password(self.data["password1"]))
        self.assertEqual(
            authenticate(username=user.username, password=self.data["password1"]),
            user,
        )

    def test_invalid_usernames_are_rejected(self):
        for username in ("", "dua kata", "<script>alert(1)</script>", "a" * 151):
            with self.subTest(username=username):
                form = RegistrationForm(data={**self.data, "username": username})

                self.assertFalse(form.is_valid())
                self.assertIn("username", form.errors)
                self.assertEqual(User.objects.count(), 0)

    def test_invalid_passwords_are_rejected(self):
        cases = (
            ("", ""),
            (self.data["password1"], "kata-sandi-berbeda"),
            ("password", "password"),
            ("aB7!", "aB7!"),
            ("7284619350", "7284619350"),
            ("pengguna_baru", "pengguna_baru"),
        )
        for password1, password2 in cases:
            with self.subTest(password1=password1, password2=password2):
                form = RegistrationForm(
                    data={**self.data, "password1": password1, "password2": password2}
                )

                self.assertFalse(form.is_valid())
                self.assertTrue({"password1", "password2"}.intersection(form.errors))
                self.assertEqual(User.objects.count(), 0)

    def test_existing_username_and_case_variant_are_rejected(self):
        User.objects.create_user(username="TetanggaKos")

        for username in ("TetanggaKos", "tetanggakos"):
            with self.subTest(username=username):
                form = RegistrationForm(data={**self.data, "username": username})

                self.assertFalse(form.is_valid())
                self.assertIn("username", form.errors)
                self.assertEqual(User.objects.count(), 1)

    def test_empty_form_is_invalid(self):
        form = RegistrationForm(data={})

        self.assertFalse(form.is_valid())
        for field in ("username", "password1", "password2"):
            self.assertIn(field, form.errors)
        self.assertEqual(User.objects.count(), 0)

    def test_invalid_form_does_not_render_password_values(self):
        form = RegistrationForm(
            data={**self.data, "password2": "kata-sandi-berbeda"}
        )
        self.assertFalse(form.is_valid())

        html = form.as_p()

        self.assertNotIn(self.data["password1"], html)
        self.assertNotIn("kata-sandi-berbeda", html)


class RegistrationViewTests(TestCase):
    """Tes request, template, CSRF, redirect, dan transaksi registrasi."""

    def setUp(self):
        self.url = reverse("userprofile:register")
        self.data = {
            "username": "pengguna_baru",
            "password1": "Q7!mango-river-planet",
            "password2": "Q7!mango-river-planet",
        }

    def test_successful_registration_creates_user_and_profile(self):
        response = self.client.post(self.url, self.data)

        self.assertRedirects(response, reverse("landing_page"))
        user = User.objects.get(username=self.data["username"])
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(UserProfile.objects.count(), 1)
        self.assertEqual(user.profile.user_id, user.pk)
        self.assertEqual(user.profile.whatsapp_number, "")
        self.assertEqual(user.profile.line_id, "")
        self.assertIsNone(user.profile.default_latitude)
        self.assertIsNone(user.profile.default_longitude)
        self.assertTrue(user.check_password(self.data["password1"]))
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertTrue(
            any(message.level == SUCCESS for message in get_messages(response.wsgi_request))
        )

    def test_landing_page_links_to_registration(self):
        response = self.client.get(reverse("landing_page"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "index.html")
        self.assertContains(response, f'href="{self.url}"')

    def test_registration_page_displays_form_and_csrf_token(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "userprofile/register.html")
        for field in ("username", "password1", "password2", "csrfmiddlewaretoken"):
            self.assertContains(response, f'name="{field}"')
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(UserProfile.objects.count(), 0)

    def test_invalid_post_displays_errors_without_creating_account(self):
        cases = (
            {},
            {**self.data, "username": "dua kata"},
            {**self.data, "password2": "kata-sandi-berbeda"},
            {**self.data, "password1": "password", "password2": "password"},
        )
        for payload in cases:
            with self.subTest(payload=payload):
                response = self.client.post(self.url, payload)

                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "userprofile/register.html")
                self.assertTrue(response.context["form"].errors)
                self.assertContains(response, "Periksa kembali isianmu.")
                self.assertNotContains(response, self.data["password1"])
                self.assertNotContains(response, "kata-sandi-berbeda")
                self.assertEqual(User.objects.count(), 0)
                self.assertEqual(UserProfile.objects.count(), 0)

    def test_valid_csrf_post_shows_success_message_on_landing_page(self):
        client = Client(enforce_csrf_checks=True)
        page = client.get(self.url)
        self.assertEqual(page.status_code, 200)
        token = client.cookies["csrftoken"].value

        response = client.post(
            self.url,
            {**self.data, "csrfmiddlewaretoken": token},
            follow=True,
        )

        self.assertRedirects(response, reverse("landing_page"))
        self.assertContains(response, "Akun berhasil dibuat.")
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(UserProfile.objects.count(), 1)

    def test_username_taken_after_validation_returns_form_error(self):
        original_is_valid = RegistrationForm.is_valid

        def validate_then_reserve_username(form):
            valid = original_is_valid(form)
            # Simulasi request lain mengambil username sesudah validasi kita.
            User.objects.create_user(username=form.cleaned_data["username"])
            return valid

        with patch.object(
            RegistrationForm,
            "is_valid",
            autospec=True,
            side_effect=validate_then_reserve_username,
        ):
            response = self.client.post(self.url, self.data)

        self.assertEqual(response.status_code, 200)
        self.assertIn("username", response.context["form"].errors)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(UserProfile.objects.count(), 0)
        self.assertFalse(User.objects.get().has_usable_password())

    def test_registration_ignores_injected_privileges_and_profile_data(self):
        response = self.client.post(
            self.url,
            {
                **self.data,
                "is_staff": "true",
                "is_superuser": "true",
                "whatsapp_number": "628123456789",
                "default_latitude": "-6.360000",
                "default_longitude": "106.820000",
            },
        )

        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username=self.data["username"])
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.groups.exists())
        self.assertFalse(user.user_permissions.exists())
        self.assertEqual(user.profile.whatsapp_number, "")
        self.assertIsNone(user.profile.default_latitude)
        self.assertIsNone(user.profile.default_longitude)

    def test_logged_in_user_cannot_register_another_account(self):
        user = User.objects.create_user(username="sudah_login")
        self.client.force_login(user)

        for method in ("get", "post"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(self.url, self.data)

                self.assertRedirects(
                    response, reverse("landing_page"), fetch_redirect_response=False
                )
                self.assertEqual(User.objects.count(), 1)
                self.assertEqual(UserProfile.objects.count(), 0)

                self.assertEqual(self.client.session["_auth_user_id"], str(user.pk))

    def test_unsupported_http_methods_are_rejected(self):
        for method in ("PUT", "PATCH", "DELETE"):
            with self.subTest(method=method):
                response = self.client.generic(method, self.url)

                self.assertEqual(response.status_code, 405)
                self.assertEqual(User.objects.count(), 0)
                self.assertEqual(UserProfile.objects.count(), 0)

    def test_post_without_csrf_token_is_rejected(self):
        # Client bawaan tes mengabaikan CSRF; aktifkan khusus untuk tes ini.
        client = Client(enforce_csrf_checks=True)

        response = client.post(self.url, self.data)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(UserProfile.objects.count(), 0)

    def test_profile_write_failure_rolls_back_account_creation(self):
        for error_type in (RuntimeError, IntegrityError):
            with self.subTest(error_type=error_type.__name__):
                # Simulasikan kegagalan profil setelah akun sempat disimpan.
                with patch(
                    "userprofile.views.UserProfile.objects.create",
                    side_effect=error_type("profile write failed"),
                ):
                    with self.assertRaises(error_type):
                        self.client.post(self.url, self.data)

                self.assertEqual(User.objects.count(), 0)
                self.assertEqual(UserProfile.objects.count(), 0)


class UserProfileAdminTests(TestCase):
    """Memastikan pencarian admin menelusuri username pada relasi user."""

    def test_search_finds_profile_by_username(self):
        owner = User.objects.create_user(username="tetangga_kos")
        other = User.objects.create_user(username="pengguna_lain")
        target = UserProfile.objects.create(user=owner)
        UserProfile.objects.create(user=other)
        model_admin = UserProfileAdmin(UserProfile, admin.site)

        results, _ = model_admin.get_search_results(
            RequestFactory().get("/admin/"), UserProfile.objects.all(), "tetangga"
        )

        self.assertEqual(list(results.values_list("pk", flat=True)), [target.pk])
