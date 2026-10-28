"""Integrasi identitas, email pengingat, lokasi, dan penghapusan data terkait."""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from FoodItem.models import FoodItem
from Location.models import Location
from SharedPost.models import SharedPost
from notification.models import Notification
from notification.views import generate_food_reminders, send_pending_reminder_emails
from userprofile.forms import RegistrationForm, UserProfileForm
from userprofile.models import UserProfile


User = get_user_model()


class EmailIntegrationTests(TestCase):
    def setUp(self):
        self.data = {
            "username": "pengingat_pribadi",
            "email": "pemilik@example.com",
            "password1": "Q7!mango-river-planet",
            "password2": "Q7!mango-river-planet",
        }

    def test_registration_requires_valid_email_before_account_creation(self):
        for value in ("", "email-tanpa-domain", "user@", "a" * 250 + "@example.com"):
            with self.subTest(value=value):
                response = self.client.post(reverse("userprofile:register"), self.data | {"email": value})
                self.assertEqual(response.status_code, 200)
                self.assertIn("email", response.context["form"].errors)
                self.assertFalse(User.objects.exists())
                self.assertFalse(UserProfile.objects.exists())

    def test_email_is_trimmed_and_saved_on_builtin_user(self):
        form = RegistrationForm(self.data | {"email": "  pemilik@example.com  "})
        self.assertTrue(form.is_valid(), form.errors)
        account = form.save()
        account.refresh_from_db()
        self.assertEqual(account.email, "pemilik@example.com")

    def test_legacy_user_can_login_and_is_prompted_to_complete_email(self):
        user = User.objects.create_user(username="akun_lama", password=self.data["password1"])
        response = self.client.post(reverse("userprofile:login"), {
            "username": user.username, "password": self.data["password1"],
        }, follow=True)
        self.assertContains(response, "Lengkapi email melalui Edit profil")
        self.assertEqual(self.client.session["_auth_user_id"], str(user.pk))

    def test_invalid_email_rejects_contact_changes(self):
        user = User.objects.create_user(username="pemilik", email="awal@example.com")
        profile = UserProfile.objects.create(user=user, line_id="sebelumnya")
        self.client.force_login(user)
        for value in ("", "bukan-email"):
            response = self.client.post(reverse("userprofile:profile_edit"), {
                "email": value, "line_id": "berubah", "default_location": "",
            })
            self.assertEqual(response.status_code, 200)
            self.assertIn("email", response.context["form"].errors)
            user.refresh_from_db()
            profile.refresh_from_db()
            self.assertEqual(user.email, "awal@example.com")
            self.assertEqual(profile.line_id, "sebelumnya")

    def test_failed_profile_save_rolls_back_email_change(self):
        user = User.objects.create_user(username="pemilik", email="awal@example.com")
        UserProfile.objects.create(user=user, line_id="sebelumnya")
        self.client.force_login(user)
        with patch("userprofile.views.UserProfile.objects.update_or_create", side_effect=IntegrityError("gagal")):
            with self.assertRaises(IntegrityError):
                self.client.post(reverse("userprofile:profile_edit"), {
                    "email": "baru@example.com", "line_id": "berubah", "default_location": "",
                })
        user.refresh_from_db()
        self.assertEqual(user.email, "awal@example.com")
        self.assertEqual(user.profile.line_id, "sebelumnya")

    def test_location_deleted_after_form_validation_does_not_partially_save_profile(self):
        user = User.objects.create_user(username="pemilik", email="awal@example.com")
        profile = UserProfile.objects.create(user=user, line_id="sebelumnya")
        location = Location.objects.create(owner=user, area_name="Kampus", latitude=-6, longitude=106)
        self.client.force_login(user)
        validate = UserProfileForm.is_valid

        def validate_then_remove_location(form):
            valid = validate(form)
            Location.objects.filter(pk=location.pk).delete()
            return valid

        with patch.object(UserProfileForm, "is_valid", autospec=True, side_effect=validate_then_remove_location):
            response = self.client.post(reverse("userprofile:profile_edit"), {
                "email": "baru@example.com", "line_id": "berubah", "default_location": location.pk,
            })
        self.assertEqual(response.status_code, 404)
        user.refresh_from_db()
        profile.refresh_from_db()
        self.assertEqual(user.email, "awal@example.com")
        self.assertEqual(profile.line_id, "sebelumnya")
        self.assertIsNone(profile.default_location_id)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_saved_email_is_used_by_expiry_reminder_and_never_leaks_to_contact(self):
        self.client.post(reverse("userprofile:register"), self.data)
        user = User.objects.get(username=self.data["username"])
        self.client.force_login(user)
        response = self.client.post(reverse("userprofile:profile_edit"), {
            "email": "alamat-baru@example.com", "line_id": "kontak.line", "default_location": "",
        })
        self.assertEqual(response.status_code, 302)
        FoodItem.objects.create(
            owner=user, name="Apel", purchase_date=timezone.localdate(),
            expiration_date=timezone.localdate() + timedelta(days=3),
        )
        self.assertEqual(generate_food_reminders()["created"], 1)
        self.assertEqual(send_pending_reminder_emails()["sent"], 1)
        self.assertEqual(mail.outbox[0].to, ["alamat-baru@example.com"])
        other = User.objects.create_user(username="tetangga")
        self.client.force_login(other)
        response = self.client.get(reverse("userprofile:donor_contact", args=[user.pk]))
        self.assertContains(response, "kontak.line")
        self.assertNotContains(response, "alamat-baru@example.com")
        self.assertNotContains(response, self.data["email"])


class AccountCascadeIntegrationTests(TestCase):
    def setUp(self):
        self.password = "J9!mango-leaf-river"
        self.user = User.objects.create_user(username="pemilik", password=self.password)
        self.location = Location.objects.create(owner=self.user, area_name="Rumah", latitude=-6, longitude=106)
        self.profile = UserProfile.objects.create(user=self.user, default_location=self.location)
        self.food = FoodItem.objects.create(
            owner=self.user, name="Apel", status="OFFERED", purchase_date=timezone.localdate(),
            expiration_date=timezone.localdate() + timedelta(days=3),
        )
        self.post = SharedPost.objects.create(food_item=self.food, location=self.location, description="Ambil sore ini di depan gang.")
        self.notification = Notification.objects.create(recipient=self.user, food_item=self.food, title="Pengingat", message="Periksa apel.")
        self.other = User.objects.create_user(username="tetangga")
        self.other_location = Location.objects.create(owner=self.other, area_name="Kampus", latitude=-7, longitude=107)
        self.client.force_login(self.user)

    def test_confirmed_account_deletion_cascades_all_owned_modules(self):
        response = self.client.post(reverse("userprofile:delete_account"), {"password": self.password, "confirm": "on"})
        self.assertRedirects(response, reverse("landing_page"))
        for model, obj in ((User, self.user), (UserProfile, self.profile), (Location, self.location), (FoodItem, self.food), (SharedPost, self.post), (Notification, self.notification)):
            self.assertFalse(model.objects.filter(pk=obj.pk).exists())
        self.assertTrue(User.objects.filter(pk=self.other.pk).exists())
        self.assertTrue(Location.objects.filter(pk=self.other_location.pk).exists())
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_foreign_post_reference_prevents_deleting_another_users_data(self):
        # Historical/admin data could contain a foreign pickup location.
        foreign_food = FoodItem.objects.create(owner=self.other, name="Roti", purchase_date=timezone.localdate(), expiration_date=timezone.localdate() + timedelta(days=1))
        foreign_post = SharedPost.objects.create(food_item=foreign_food, location=self.location, description="Penawaran lama dari tetangga.")
        response = self.client.post(reverse("userprofile:delete_account"), {"password": self.password, "confirm": "on"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].non_field_errors())
        for model, obj in ((User, self.user), (UserProfile, self.profile), (Location, self.location), (FoodItem, self.food), (SharedPost, self.post), (Notification, self.notification), (SharedPost, foreign_post)):
            self.assertTrue(model.objects.filter(pk=obj.pk).exists())
        self.assertEqual(self.client.session["_auth_user_id"], str(self.user.pk))
