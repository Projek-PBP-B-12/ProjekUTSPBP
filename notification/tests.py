from datetime import date, timedelta
from smtplib import SMTPException
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from FoodItem.models import FoodItem
from .models import Notification
from .views import (
    generate_food_reminders,
    send_pending_reminder_emails,
    send_reminder_email,
)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="TitikLapar <noreply@example.com>",
    SITE_URL="https://titiklapar.example",
)
class FoodReminderTests(TestCase):
    def setUp(self):
        self.today = date(2030, 5, 10)
        clock = patch(
            "notification.views.timezone.localdate",
            return_value=self.today,
        )
        clock.start()
        self.addCleanup(clock.stop)
        self.user = get_user_model().objects.create_user(
            username="owner_test", email="owner@example.com",
        )
        self.other = get_user_model().objects.create_user(
            username="other_test", email="other@example.com",
        )

    def make_food(self, days=7, status="STORED", owner=None):
        return FoodItem.objects.create(
            owner=owner or self.user,
            name=f"Bayam uji H-{days}",
            purchase_date=self.today,
            expiration_date=self.today + timedelta(days=days),
            status=status,
        )


    def test_only_h7_h3_h1_are_generated(self):
        for days in (7, 3, 1, 2, 0, -1):
            self.make_food(days=days)
        result = generate_food_reminders()
        self.assertEqual(result, {"checked": 3, "created": 3})
        self.assertSetEqual(
            set(Notification.objects.values_list("reminder_days", flat=True)),
            {7, 3, 1},
        )

    def test_repeat_run_does_not_duplicate(self):
        self.make_food()
        generate_food_reminders()
        self.assertEqual(generate_food_reminders()["created"], 0)
        self.assertEqual(Notification.objects.count(), 1)

    def test_database_prevents_duplicate_stage(self):
        self.make_food()
        generate_food_reminders()
        original = Notification.objects.get()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Notification.objects.create(
                    recipient=original.recipient,
                    food_item=original.food_item,
                    reminder_days=original.reminder_days,
                    expiry_date=original.expiry_date,
                    title="Duplikat", message="Duplikat",
                )

    def test_recipient_is_food_owner(self):
        self.make_food(owner=self.other)
        generate_food_reminders()
        self.assertEqual(Notification.objects.get().recipient_id, self.other.pk)

    def test_offered_food_is_still_active(self):
        self.make_food(status="OFFERED")
        self.assertEqual(generate_food_reminders()["created"], 1)

    def test_consumed_food_is_excluded(self):
        self.make_food(status="CONSUMED")
        self.assertEqual(generate_food_reminders()["created"], 0)

    def test_consumed_after_h7_stops_h3(self):
        food = self.make_food()
        generate_food_reminders()
        food.status = "CONSUMED"
        food.save(update_fields=["status"])
        with patch(
            "notification.views.timezone.localdate",
            return_value=self.today + timedelta(days=4),
        ):
            self.assertEqual(generate_food_reminders()["created"], 0)
        self.assertEqual(Notification.objects.count(), 1)

    def test_deleted_after_h7_stops_h3_but_keeps_history(self):
        food = self.make_food()
        generate_food_reminders()
        food.delete()
        with patch(
            "notification.views.timezone.localdate",
            return_value=self.today + timedelta(days=4),
        ):
            self.assertEqual(generate_food_reminders()["created"], 0)
        self.assertIsNone(Notification.objects.get().food_item_id)

    def test_read_h7_does_not_cancel_h3(self):
        self.make_food()
        generate_food_reminders()
        Notification.objects.update(is_read=True)
        with patch(
            "notification.views.timezone.localdate",
            return_value=self.today + timedelta(days=4),
        ):
            self.assertEqual(generate_food_reminders()["created"], 1)
        self.assertTrue(Notification.objects.filter(
            reminder_days=3, is_read=False,
        ).exists())

    def test_changed_expiry_uses_new_schedule(self):
        food = self.make_food()
        generate_food_reminders()
        food.expiration_date = self.today + timedelta(days=9)
        food.save(update_fields=["expiration_date"])
        with patch(
            "notification.views.timezone.localdate",
            return_value=self.today + timedelta(days=2),
        ):
            self.assertEqual(generate_food_reminders()["created"], 1)
        self.assertEqual(Notification.objects.filter(reminder_days=7).count(), 2)

    def test_dry_run_never_writes_or_sends(self):
        self.make_food()
        result = generate_food_reminders(dry_run=True)
        self.assertEqual(result, {"checked": 1, "created": 0})
        self.assertEqual(Notification.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_generation_queues_without_sending(self):
        self.make_food()
        generate_food_reminders()
        notification = Notification.objects.get()
        self.assertEqual(notification.email_status, Notification.EmailStatus.PENDING)
        self.assertEqual(len(mail.outbox), 0)

    def test_pending_email_sends_once_to_food_owner(self):
        self.make_food()
        generate_food_reminders()
        self.assertEqual(send_pending_reminder_emails()["sent"], 1)
        self.assertEqual(send_pending_reminder_emails()["sent"], 0)
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])
        self.assertIn("H-7", mail.outbox[0].subject)
        self.assertIn("https://titiklapar.example/notification/", mail.outbox[0].body)
        notification = Notification.objects.get()
        self.assertEqual(notification.email_status, Notification.EmailStatus.SENT)
        self.assertIsNotNone(notification.email_sent_at)

    def test_manual_history_is_not_emailed(self):
        for _ in range(2):
            Notification.objects.create(
                recipient=self.user, title="Manual", message="Riwayat",
            )
        generate_food_reminders()
        send_pending_reminder_emails()
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(Notification.objects.count(), 2)

    def test_smtp_failure_is_recorded_and_can_retry(self):
        self.make_food()
        generate_food_reminders()
        notification = Notification.objects.get()
        with patch(
            "notification.views.send_mail",
            side_effect=SMTPException("Koneksi uji gagal"),
        ):
            result = send_reminder_email(notification.pk)
        self.assertEqual(result, Notification.EmailStatus.FAILED)
        notification.refresh_from_db()
        self.assertIn("Koneksi uji gagal", notification.last_email_error)
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(send_pending_reminder_emails()["sent"], 1)
        notification.refresh_from_db()
        self.assertEqual(notification.last_email_error, "")

    def test_network_timeout_keeps_website_notification(self):
        self.make_food()
        generate_food_reminders()
        notification = Notification.objects.get()
        with patch(
            "notification.views.send_mail", side_effect=TimeoutError("Uji timeout"),
        ):
            self.assertEqual(
                send_reminder_email(notification.pk), Notification.EmailStatus.FAILED,
            )
        self.assertTrue(Notification.objects.filter(pk=notification.pk).exists())

    def test_pending_summary_reports_email_failure(self):
        self.make_food()
        generate_food_reminders()
        with patch(
            "notification.views.send_mail", side_effect=SMTPException("Uji gagal"),
        ):
            result = send_pending_reminder_emails()
        self.assertEqual(result, {"sent": 0, "failed": 1, "skipped": 0})
        self.assertEqual(
            Notification.objects.get().email_status, Notification.EmailStatus.FAILED,
        )

    def test_zero_messages_accepted_is_recorded_as_failure(self):
        self.make_food()
        generate_food_reminders()
        with patch("notification.views.send_mail", return_value=0):
            self.assertEqual(
                send_pending_reminder_emails()["failed"], 1,
            )

    def test_consumed_before_delivery_is_skipped(self):
        food = self.make_food()
        generate_food_reminders()
        food.status = "CONSUMED"
        food.save(update_fields=["status"])
        self.assertEqual(send_pending_reminder_emails()["skipped"], 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_deleted_before_delivery_is_skipped(self):
        food = self.make_food()
        generate_food_reminders()
        food.delete()
        self.assertEqual(send_pending_reminder_emails()["skipped"], 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_changed_owner_before_delivery_is_skipped(self):
        food = self.make_food()
        generate_food_reminders()
        food.owner = self.other
        food.save(update_fields=["owner"])
        self.assertEqual(send_pending_reminder_emails()["skipped"], 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_changed_expiry_before_delivery_is_skipped(self):
        food = self.make_food()
        generate_food_reminders()
        food.expiration_date = self.today + timedelta(days=10)
        food.save(update_fields=["expiration_date"])
        self.assertEqual(send_pending_reminder_emails()["skipped"], 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_old_failed_stage_is_not_sent_after_its_day(self):
        self.make_food()
        generate_food_reminders()
        Notification.objects.update(email_status=Notification.EmailStatus.FAILED)
        with patch(
            "notification.views.timezone.localdate",
            return_value=self.today + timedelta(days=1),
        ):
            self.assertEqual(send_pending_reminder_emails()["skipped"], 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_invalid_or_empty_recipient_email_is_skipped(self):
        for invalid_email in ("", "not-an-email"):
            with self.subTest(email=invalid_email):
                food = self.make_food()
                self.user.email = invalid_email
                self.user.save(update_fields=["email"])
                generate_food_reminders()
                notification = Notification.objects.get(food_item=food)
                self.assertEqual(
                    send_reminder_email(notification.pk), Notification.EmailStatus.SKIPPED,
                )
        self.assertEqual(len(mail.outbox), 0)

    def test_read_status_does_not_cancel_pending_email(self):
        self.make_food()
        generate_food_reminders()
        Notification.objects.update(is_read=True)
        self.assertEqual(send_pending_reminder_emails()["sent"], 1)

    def test_missing_notification_is_skipped(self):
        self.assertEqual(
            send_reminder_email(999999), Notification.EmailStatus.SKIPPED,
        )

    def test_page_shows_only_current_user_with_stage_and_expiry(self):
        food = self.make_food()
        self.make_food(owner=self.other)
        generate_food_reminders()
        other_notification = Notification.objects.get(recipient=self.other)
        other_notification.title = "Pesan privat pengguna lain"
        other_notification.save(update_fields=["title"])
        self.client.force_login(self.user)
        response = self.client.get(reverse("notification:show_notification"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["unread_count"], 1)
        self.assertContains(response, "H-7")
        self.assertContains(response, food.expiration_date.strftime("%d/%m/%Y"))
        self.assertNotContains(response, other_notification.title)

    def test_mark_read_updates_count_but_does_not_send_email(self):
        self.make_food()
        generate_food_reminders()
        notification = Notification.objects.get()
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("notification:mark_read", args=[notification.pk]),
        )
        self.assertEqual(response.json(), {"success": True, "unread_count": 0})
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)
        self.assertEqual(notification.email_status, Notification.EmailStatus.PENDING)
        self.assertEqual(len(mail.outbox), 0)

    def test_other_user_cannot_mark_notification_read(self):
        self.make_food()
        generate_food_reminders()
        notification = Notification.objects.get()
        self.client.force_login(self.other)
        response = self.client.post(
            reverse("notification:mark_read", args=[notification.pk]),
        )
        self.assertEqual(response.status_code, 404)
        notification.refresh_from_db()
        self.assertFalse(notification.is_read)

    def test_authentication_and_post_method_are_required(self):
        self.make_food()
        generate_food_reminders()
        notification = Notification.objects.get()
        url = reverse("notification:mark_read", args=[notification.pk])
        self.assertEqual(self.client.post(url).status_code, 401)
        self.assertEqual(
            self.client.get(reverse("notification:show_notification")).status_code, 302,
        )
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_csrf_token_is_required_and_valid_token_works(self):
        self.make_food()
        generate_food_reminders()
        notification = Notification.objects.get()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        client.get(reverse("notification:show_notification"))
        url = reverse("notification:mark_read", args=[notification.pk])
        self.assertEqual(client.post(url).status_code, 403)
        token = client.cookies["csrftoken"].value
        self.assertEqual(client.post(url, HTTP_X_CSRFTOKEN=token).status_code, 200)

    def test_read_card_has_disabled_button_without_post_form(self):
        self.make_food()
        generate_food_reminders()
        Notification.objects.update(is_read=True)
        self.client.force_login(self.user)
        response = self.client.get(reverse("notification:show_notification"))
        self.assertContains(
            response,
            '<button class="notif-read-button" type="button" disabled>Sudah dibaca</button>',
            html=True,
        )
        self.assertNotContains(response, 'class="notif-read-form"')

    def test_manual_card_without_food_or_stage_still_renders(self):
        Notification.objects.create(
            recipient=self.user, title="Pesan manual lama", message="Riwayat lama.",
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("notification:show_notification"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pesan manual lama")
        self.assertNotContains(response, "Perkiraan kedaluwarsa:")

    def test_delivery_result_does_not_overwrite_concurrent_read_status(self):
        self.make_food()
        generate_food_reminders()
        notification = Notification.objects.get()

        def accept_email(**kwargs):
            Notification.objects.filter(pk=notification.pk).update(is_read=True)
            return 1

        with patch("notification.views.send_mail", side_effect=accept_email):
            self.assertEqual(
                send_reminder_email(notification.pk), Notification.EmailStatus.SENT,
            )
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)


class NotificationNavigationTests(TestCase):
    def test_guest_uses_user_login_and_preserves_destination(self):
        url = reverse("notification:show_notification")
        response = self.client.get(url)
        self.assertRedirects(
            response,
            reverse("userprofile:login") + "?next=" + url,
            fetch_redirect_response=False,
        )

    def test_non_staff_user_has_all_sidebar_links(self):
        from html.parser import HTMLParser

        class SidebarParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.links = []

            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == "a" and "notif-nav-item" in attrs.get("class", "").split():
                    self.links.append(attrs.get("href"))

        user = get_user_model().objects.create_user(username="navigation_user")
        self.client.force_login(user)
        response = self.client.get(reverse("notification:show_notification"))
        self.assertEqual(response.status_code, 200)
        parser = SidebarParser()
        parser.feed(response.content.decode())
        routes = [
            "landing_page", "FoodItem:makananku", "FoodItem:add_food_item",
            "sharedpost:list", "Location:map", "notification:show_notification",
            "userprofile:profile",
        ]
        self.assertEqual(parser.links, [reverse(route) for route in routes])
        self.assertNotContains(response, 'aria-disabled="true"')


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class FoodNotificationIntegrationTests(TestCase):
    def setUp(self):
        self.today = date(2030, 5, 10)
        clock = patch("notification.views.timezone.localdate", return_value=self.today)
        clock.start()
        self.addCleanup(clock.stop)
        self.user = get_user_model().objects.create_user(
            username="food_integration", email="owner@example.com",
        )
        self.other = get_user_model().objects.create_user(username="other_food_owner")
        self.client.force_login(self.user)

    def food_data(self, days):
        return {
            "name": "Mangga integrasi", "category": "FRUIT",
            "purchase_date": self.today.isoformat(),
            "expiration_date": (self.today + timedelta(days=days)).isoformat(),
            "image_url": "",
        }

    def make_food(self, days, owner=None):
        return FoodItem.objects.create(
            owner=owner or self.user, name="Makanan lama", category="FRUIT",
            purchase_date=self.today,
            expiration_date=self.today + timedelta(days=days),
        )

    def test_add_food_creates_each_due_stage_and_sends_to_owner(self):
        for days in (7, 3, 1):
            response = self.client.post(reverse("FoodItem:add_food_item"), self.food_data(days))
            self.assertEqual(response.status_code, 302)
            food = FoodItem.objects.latest("pk")
            notification = Notification.objects.get(food_item=food)
            self.assertEqual(notification.recipient_id, self.user.pk)
            self.assertEqual(notification.reminder_days, days)
            self.assertEqual(notification.email_status, Notification.EmailStatus.SENT)
        self.assertEqual(len(mail.outbox), 3)
        self.assertTrue(all(email.to == [self.user.email] for email in mail.outbox))

    def test_add_food_outside_stages_does_not_create_early_reminder(self):
        self.client.post(reverse("FoodItem:add_food_item"), self.food_data(5))
        self.assertEqual(FoodItem.objects.count(), 1)
        self.assertFalse(Notification.objects.exists())

    def test_edit_to_due_date_creates_once(self):
        food = self.make_food(5)
        url = reverse("FoodItem:change_food_item", args=[food.pk])
        for _ in range(2):
            response = self.client.post(url, self.food_data(1))
            self.assertEqual(response.status_code, 302)
        self.assertEqual(Notification.objects.filter(food_item=food).count(), 1)
        self.assertEqual(Notification.objects.get().reminder_days, 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_opening_notifications_backfills_only_current_user_without_duplicates(self):
        food = self.make_food(1)
        self.make_food(1, owner=self.other)
        for _ in range(2):
            response = self.client.get(reverse("notification:show_notification"))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Pengingat H-1: Makanan lama")
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(Notification.objects.get().food_item_id, food.pk)
        self.assertEqual(len(mail.outbox), 0)

    def test_consumed_food_does_not_get_backfilled(self):
        food = self.make_food(1)
        food.status = "CONSUMED"
        food.save(update_fields=["status"])
        self.client.get(reverse("notification:show_notification"))
        self.assertFalse(Notification.objects.exists())

    def test_guest_cannot_trigger_backfill(self):
        self.make_food(1)
        self.client.logout()
        response = self.client.get(reverse("notification:show_notification"))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Notification.objects.exists())


    def test_smtp_failure_does_not_lose_food_or_website_notification(self):
        with patch("notification.views.send_mail", side_effect=SMTPException("SMTP uji gagal")):
            response = self.client.post(reverse("FoodItem:add_food_item"), self.food_data(1))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(FoodItem.objects.count(), 1)
        notification = Notification.objects.get()
        self.assertEqual(notification.email_status, Notification.EmailStatus.FAILED)
        self.assertIn("SMTP uji gagal", notification.last_email_error)

    def test_saving_one_food_does_not_send_other_users_pending_email(self):
        other_food = self.make_food(1, owner=self.other)
        generate_food_reminders(food_item=other_food)
        self.client.post(reverse("FoodItem:add_food_item"), self.food_data(1))
        self.assertEqual(Notification.objects.get(food_item=other_food).email_status,
                         Notification.EmailStatus.PENDING)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])

    def test_invalid_recipient_keeps_website_notification_without_email(self):
        self.user.email = ""
        self.user.save(update_fields=["email"])
        response = self.client.post(reverse("FoodItem:add_food_item"), self.food_data(1))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Notification.objects.get().email_status, Notification.EmailStatus.SKIPPED)
        self.assertEqual(len(mail.outbox), 0)
