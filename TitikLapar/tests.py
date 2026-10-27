from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from FoodItem.models import FoodItem
from Location.models import Location
from SharedPost.models import SharedPost
from notification.models import Notification


class DashboardTests(TestCase):
    today = date(2030, 1, 15)

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="dashboard_user")
        cls.other = get_user_model().objects.create_user(username="other_dashboard_user")

    def setUp(self):
        self.client.force_login(self.user)
        self.clock = patch("TitikLapar.views.timezone.localdate", return_value=self.today)
        self.clock.start()
        self.addCleanup(self.clock.stop)

    def food(self, status="STORED", days=10, owner=None):
        return FoodItem.objects.create(
            owner=owner or self.user, name="Makanan contoh", status=status,
            purchase_date=self.today - timedelta(days=5),
            expiration_date=self.today + timedelta(days=days),
        )

    def post(self, food, active=True):
        location = Location.objects.create(
            owner=food.owner, area_name="Beji", latitude="-6.36", longitude="106.83",
        )
        return SharedPost.objects.create(
            food_item=food, location=location, is_active=active,
            description="Ambil di lobi kos sore hari.",
        )

    def test_guest_still_gets_public_landing_page(self):
        self.client.logout()
        response = self.client.get(reverse("landing_page"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "index.html")
        self.assertNotContains(response, "Quick Notification")

    def test_new_user_gets_zero_counts_and_empty_notifications(self):
        response = self.client.get(reverse("landing_page"))
        self.assertTemplateUsed(response, "dashboard.html")
        self.assertTemplateUsed(response, "base.html")
        self.assertEqual(response.context["stored_count"], 0)
        self.assertEqual(response.context["attention_count"], 0)
        self.assertEqual(response.context["shared_count"], 0)
        self.assertContains(response, "Selamat Datang, dashboard_user")
        self.assertContains(response, "Belum ada notifikasi baru")
        self.assertContains(response, "Belum ada yang perlu segera diperiksa")
        self.assertContains(response, "Mulai berbagi dari kulkasmu")
        self.assertContains(response, f'href="{reverse("FoodItem:add_food_item")}"')
        self.assertContains(response, f'href="{reverse("sharedpost:create")}"')

    def test_summary_uses_only_current_users_food(self):
        self.food(days=1)
        self.food(days=3)
        self.food(days=10)
        self.post(self.food(status="OFFERED", days=9))
        self.post(self.food(owner=self.other, status="OFFERED", days=1))
        self.food(owner=self.other, days=1)
        self.food(status="CONSUMED", days=1)
        response = self.client.get(reverse("landing_page"))
        self.assertEqual(response.context["stored_count"], 3)
        self.assertEqual(response.context["attention_count"], 2)
        self.assertEqual(response.context["shared_count"], 1)

    def test_attention_includes_today_and_day_three_but_not_expired(self):
        for days in [-1, 0, 3, 4]:
            self.food(days=days)
        self.food(status="OFFERED", days=2)
        self.food(status="CONSUMED", days=1)
        response = self.client.get(reverse("landing_page"))
        self.assertEqual(response.context["attention_count"], 3)
        self.assertEqual(response.context["stored_count"], 4)

    def test_shared_count_excludes_closed_expired_and_nonoffered(self):
        self.post(self.food(status="OFFERED", days=0))
        self.post(self.food(status="OFFERED", days=-1))
        self.post(self.food(status="OFFERED", days=2), active=False)
        self.post(self.food(status="STORED", days=2))
        self.post(self.food(status="CONSUMED", days=2), active=False)
        response = self.client.get(reverse("landing_page"))
        self.assertEqual(response.context["shared_count"], 1)

    def test_notifications_are_latest_three_unread_and_private(self):
        expected = []
        for number in range(4):
            expected.append(Notification.objects.create(
                recipient=self.user, title=f"Pengingat {number}", message="Cek makananmu.",
            ))
        Notification.objects.create(recipient=self.user, title="Sudah dibaca", message="Pesan lama", is_read=True)
        Notification.objects.create(recipient=self.other, title="Pesan rahasia pengguna lain", message="Pribadi")
        response = self.client.get(reverse("landing_page"))
        self.assertEqual(list(response.context["quick_notifications"]), list(reversed(expected))[:3])
        self.assertNotContains(response, "Sudah dibaca")
        self.assertNotContains(response, "Pesan rahasia pengguna lain")
        self.assertEqual(Notification.objects.filter(recipient=self.user, is_read=False).count(), 4)

    def test_attention_preview_prioritizes_three_nearest_owned_foods(self):
        later = self.food(days=2)
        today = self.food(days=0)
        tomorrow = self.food(status="OFFERED", days=1)
        self.food(days=3)
        self.food(days=4)
        self.food(days=-1)
        self.food(status="CONSUMED", days=0)
        self.food(owner=self.other, days=0)

        response = self.client.get(reverse("landing_page"))

        self.assertEqual(list(response.context["attention_foods"]), [today, tomorrow, later])
        self.assertEqual(response.context["attention_count"], 4)
        self.assertContains(response, "Hari ini")
        self.assertContains(response, "Besok")
        for food in [today, tomorrow, later]:
            self.assertContains(response, f'href="{reverse("FoodItem:change_food_item", args=[food.pk])}"')

    def test_offers_preview_only_shows_three_available_owned_posts(self):
        later = self.post(self.food(status="OFFERED", days=3))
        today = self.post(self.food(status="OFFERED", days=0))
        sooner = self.post(self.food(status="OFFERED", days=2))
        self.post(self.food(status="OFFERED", days=4))
        self.post(self.food(status="OFFERED", days=1), active=False)
        self.post(self.food(status="OFFERED", days=-1))
        self.post(self.food(status="STORED", days=1))
        other = self.post(self.food(owner=self.other, status="OFFERED", days=0))

        response = self.client.get(reverse("landing_page"))

        self.assertEqual(list(response.context["active_posts"]), [today, sooner, later])
        self.assertEqual(response.context["shared_count"], 4)
        for post in [today, sooner, later]:
            self.assertContains(response, f'href="{reverse("sharedpost:detail", args=[post.pk])}"')
        self.assertNotContains(response, f'href="{reverse("sharedpost:detail", args=[other.pk])}"')

    def test_display_name_uses_full_name_and_escapes_html(self):
        self.user.first_name = "Jane"
        self.user.last_name = "Doe"
        self.user.save()
        self.assertContains(self.client.get(reverse("landing_page")), "Selamat Datang, Jane Doe")
        self.user.first_name = "<script>alert(1)</script>"
        self.user.save()
        response = self.client.get(reverse("landing_page"))
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;")

    def test_dashboard_links_logout_and_no_side_effects(self):
        self.food(days=1)
        before = (FoodItem.objects.count(), Notification.objects.count(), SharedPost.objects.count())
        with patch("notification.views.send_mail") as send_mail:
            response = self.client.get(reverse("landing_page"))
        send_mail.assert_not_called()
        self.assertEqual(before, (FoodItem.objects.count(), Notification.objects.count(), SharedPost.objects.count()))
        for url in [reverse("FoodItem:makananku"), reverse("sharedpost:list")+"?mine=1", reverse("userprofile:profile")]:
            self.assertContains(response, f'href="{url}"')
        self.assertContains(response, f'action="{reverse("userprofile:logout")}"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertIn("no-store", response["Cache-Control"])
