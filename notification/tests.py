from datetime import timedelta
from io import StringIO
from smtplib import SMTPException
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from FoodItem.models import FoodItem
from .models import Notification
from .views import generate_food_reminders, send_pending_reminder_emails, send_reminder_email


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class NotificationIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            username="notification-owner", email="owner@example.com", password="TestPassword123!",
        )
        cls.other = get_user_model().objects.create_user(
            username="notification-other", email="other@example.com", password="OtherPassword123!",
        )

    def food(self, days=3, **kwargs):
        values = {
            "owner": self.owner,
            "name": "Apel",
            "purchase_date": timezone.localdate() - timedelta(days=2),
            "expiration_date": timezone.localdate() + timedelta(days=days),
            "status": "STORED",
        }
        values.update(kwargs)
        return FoodItem.objects.create(**values)

    def reminder(self, food=None, **kwargs):
        food = food or self.food()
        values = {
            "recipient": food.owner,
            "food_item": food,
            "title": "Pengingat H-3: Apel",
            "message": "Periksa kondisi makananmu.",
            "reminder_days": 3,
            "expiry_date": food.expiration_date,
            "email_status": Notification.EmailStatus.PENDING,
        }
        values.update(kwargs)
        return Notification.objects.create(**values)

    def test_page_redirects_to_regular_login(self):
        url = reverse("notification:show_notification")
        self.assertRedirects(
            self.client.get(url), reverse("userprofile:login") + "?next=" + url,
        )

    def test_page_shows_only_own_notifications_and_private_email(self):
        own = self.reminder(title="Pesan milikku")
        self.reminder(food=self.food(owner=self.other), title="Pesan rahasia pengguna lain")
        self.client.force_login(self.owner)
        response = self.client.get(reverse("notification:show_notification"))
        self.assertContains(response, own.title)
        self.assertContains(response, self.owner.email)
        self.assertNotContains(response, "Pesan rahasia pengguna lain")
        self.assertNotContains(response, self.other.email)
        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_legacy_account_without_email_gets_profile_link(self):
        self.owner.email = ""
        self.owner.save(update_fields=["email"])
        self.client.force_login(self.owner)
        response = self.client.get(reverse("notification:show_notification"))
        self.assertContains(response, "Tambahkan email")
        self.assertContains(response, reverse("userprofile:profile_edit"))

    def test_get_page_refreshes_only_own_reminders_without_sending_email(self):
        food = self.food()
        self.food(owner=self.other)
        self.client.force_login(self.owner)
        with patch("notification.views.send_mail") as send:
            self.client.get(reverse("notification:show_notification"))
            self.client.get(reverse("notification:show_notification"))
        send.assert_not_called()
        self.assertEqual(Notification.objects.count(), 1)
        reminder = Notification.objects.get()
        self.assertEqual(reminder.food_item, food)
        self.assertEqual(reminder.recipient, self.owner)
        self.assertEqual(reminder.email_status, Notification.EmailStatus.PENDING)
        food.refresh_from_db()
        self.assertEqual(food.status, "STORED")

    def test_generator_filters_owner_and_food_together(self):
        food = self.food()
        foreign = self.food(owner=self.other)
        self.food()
        self.assertEqual(generate_food_reminders(recipient=self.owner, food_item=foreign), {"checked": 0, "created": 0})
        self.assertEqual(generate_food_reminders(recipient=self.owner, food_item=food), {"checked": 1, "created": 1})
        self.assertEqual(Notification.objects.get().food_item, food)

    def test_food_scoped_sender_leaves_other_pending_emails_untouched(self):
        target = self.reminder()
        another = self.reminder(food=self.food())
        foreign = self.reminder(food=self.food(owner=self.other))
        result = send_pending_reminder_emails(food_item=target.food_item)
        self.assertEqual(result, {"sent": 1, "failed": 0, "skipped": 0, "in_progress": 0})
        self.assertEqual(len(mail.outbox), 1)
        for reminder in (another, foreign):
            reminder.refresh_from_db()
            self.assertEqual(reminder.email_status, Notification.EmailStatus.PENDING)

    def test_mark_read_is_owned_and_post_only(self):
        own = self.reminder()
        foreign = self.reminder(food=self.food(owner=self.other))
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse("notification:mark_read", args=[own.pk])).status_code, 405)
        self.assertEqual(self.client.post(reverse("notification:mark_read", args=[foreign.pk])).status_code, 404)
        response = self.client.post(reverse("notification:mark_read", args=[own.pk]))
        self.assertEqual(response.json(), {"success": True, "unread_count": 0})
        own.refresh_from_db()
        foreign.refresh_from_db()
        self.assertTrue(own.is_read)
        self.assertFalse(foreign.is_read)
        self.assertEqual(own.email_status, Notification.EmailStatus.PENDING)
        self.assertEqual(own.food_item.status, "STORED")

    def test_mark_read_requires_login_and_csrf(self):
        reminder = self.reminder()
        url = reverse("notification:mark_read", args=[reminder.pk])
        self.assertEqual(self.client.post(url).status_code, 401)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.owner)
        self.assertEqual(csrf_client.post(url).status_code, 403)

    def test_generate_only_h7_h3_h1_active_food_for_active_owners(self):
        for days in (7, 3, 1):
            self.food(days, name=f"Pengingat {days}")
        self.food(3, name="Ditawarkan", status="OFFERED")
        for days in (0, 2, 4, 8):
            self.food(days)
        self.food(3, status="CONSUMED")
        self.other.is_active = False
        self.other.save(update_fields=["is_active"])
        self.food(3, owner=self.other)
        result = generate_food_reminders()
        self.assertEqual(result, {"checked": 4, "created": 4})
        self.assertEqual(set(Notification.objects.values_list("reminder_days", flat=True)), {1, 3, 7})

    def test_generator_deduplicates_same_food_stage_and_expiry_date(self):
        self.food()
        self.assertEqual(generate_food_reminders()["created"], 1)
        self.assertEqual(generate_food_reminders()["created"], 0)
        self.assertEqual(Notification.objects.count(), 1)

    def test_command_dry_run_does_not_change_records_or_send_pending_email(self):
        self.reminder()
        output = StringIO()
        with patch("notification.views.send_mail") as send:
            call_command("send_food_reminders", "--dry-run", stdout=output)
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(Notification.objects.get().email_status, Notification.EmailStatus.PENDING)
        send.assert_not_called()
        self.assertIn("Dry run", output.getvalue())

    def test_command_generates_and_sends_once_on_repeat(self):
        self.food()
        call_command("send_food_reminders", stdout=StringIO())
        call_command("send_food_reminders", stdout=StringIO())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(Notification.objects.get().email_status, Notification.EmailStatus.SENT)

    def test_email_uses_current_user_email_not_old_address(self):
        reminder = self.reminder()
        self.owner.email = "new@example.com"
        self.owner.save(update_fields=["email"])
        status = send_reminder_email(reminder.pk)
        self.assertEqual(status, Notification.EmailStatus.SENT)
        self.assertEqual(mail.outbox[0].to, ["new@example.com"])
        self.assertIn(reverse("notification:show_notification"), mail.outbox[0].body)
        reminder.refresh_from_db()
        self.assertIsNotNone(reminder.email_sent_at)
        self.assertFalse(reminder.is_read)

    def test_second_worker_cannot_send_claimed_reminder(self):
        reminder = self.reminder()

        def mail_in_flight(**kwargs):
            self.assertEqual(send_reminder_email(reminder.pk), Notification.EmailStatus.SENDING)
            return 1

        with patch("notification.views.send_mail", side_effect=mail_in_flight) as send:
            self.assertEqual(send_reminder_email(reminder.pk), Notification.EmailStatus.SENT)
            self.assertEqual(send_reminder_email(reminder.pk), Notification.EmailStatus.SENT)
        send.assert_called_once()

    def test_failed_email_can_be_retried(self):
        reminder = self.reminder()
        with patch("notification.views.send_mail", side_effect=SMTPException("Connection failed")):
            self.assertEqual(send_reminder_email(reminder.pk), Notification.EmailStatus.FAILED)
        reminder.refresh_from_db()
        self.assertIn("Connection failed", reminder.last_email_error)
        self.assertIsNone(reminder.email_sent_at)
        self.assertEqual(send_reminder_email(reminder.pk), Notification.EmailStatus.SENT)
        reminder.refresh_from_db()
        self.assertEqual(reminder.last_email_error, "")

    def test_backend_zero_result_is_failure_and_command_returns_error(self):
        self.food()
        with patch("notification.views.send_mail", return_value=0):
            with self.assertRaises(CommandError):
                call_command("send_food_reminders", stdout=StringIO())
        self.assertEqual(Notification.objects.get().email_status, Notification.EmailStatus.FAILED)

    def test_missing_or_invalid_email_skips_only_email(self):
        for email in ("", "invalid email"):
            with self.subTest(email=email):
                self.owner.email = email
                self.owner.save(update_fields=["email"])
                reminder = self.reminder()
                with patch("notification.views.send_mail") as send:
                    self.assertEqual(send_reminder_email(reminder.pk), Notification.EmailStatus.SKIPPED)
                send.assert_not_called()
                self.assertTrue(Notification.objects.filter(pk=reminder.pk).exists())

    def test_inactive_recipient_is_not_emailed(self):
        reminder = self.reminder()
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        with patch("notification.views.send_mail") as send:
            self.assertEqual(send_reminder_email(reminder.pk), Notification.EmailStatus.SKIPPED)
        send.assert_not_called()

    def test_deleted_food_is_not_emailed(self):
        reminder = self.reminder()
        reminder.food_item.delete()
        with patch("notification.views.send_mail") as send:
            self.assertEqual(send_reminder_email(reminder.pk), Notification.EmailStatus.SKIPPED)
        send.assert_not_called()

    def test_stale_food_state_owner_or_expiry_is_not_emailed(self):
        changes = (
            {"status": "CONSUMED"},
            {"owner": self.other},
            {"expiration_date": timezone.localdate() + timedelta(days=4)},
        )
        for change in changes:
            with self.subTest(change=change):
                food = self.food()
                reminder = self.reminder(food=food)
                FoodItem.objects.filter(pk=food.pk).update(**change)
                with patch("notification.views.send_mail") as send:
                    self.assertEqual(send_reminder_email(reminder.pk), Notification.EmailStatus.SKIPPED)
                send.assert_not_called()

    def test_late_stage_or_non_reminder_is_not_emailed(self):
        reminders = (
            self.reminder(food=self.food(days=2)),
            self.reminder(reminder_days=None),
        )
        for reminder in reminders:
            with self.subTest(reminder=reminder.pk):
                with patch("notification.views.send_mail") as send:
                    self.assertEqual(send_reminder_email(reminder.pk), Notification.EmailStatus.SKIPPED)
                send.assert_not_called()

    def test_unknown_notification_is_skipped(self):
        self.assertEqual(send_reminder_email(999999), Notification.EmailStatus.SKIPPED)

    def test_header_newlines_are_removed_from_food_title(self):
        reminder = self.reminder(title="Apel\r\nBcc: attacker@example.com")
        send_reminder_email(reminder.pk)
        self.assertEqual(mail.outbox[0].to, [self.owner.email])
        self.assertNotIn("\n", mail.outbox[0].subject)
        self.assertNotIn("\r", mail.outbox[0].subject)
