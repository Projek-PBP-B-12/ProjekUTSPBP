from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from FoodItem.models import FoodItem
from .models import Notification


class NotificationAPITests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('notification-owner')
        self.other = get_user_model().objects.create_user('notification-other')
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + Token.objects.create(user=self.user).key)
        self.notification = Notification.objects.create(recipient=self.user,
            title='Pengingat', message='Periksa makananmu.', last_email_error='Private error')
        self.foreign = Notification.objects.create(recipient=self.other,
            title='Privat', message='Milik akun lain.')

    def test_list_detail_and_private_fields(self):
        response = self.client.get('/api/notifications/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], self.notification.pk)
        self.assertNotIn('last_email_error', response.data['results'][0])
        self.assertNotIn('recipient', response.data['results'][0])
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(self.client.get(f'/api/notifications/{self.notification.pk}/').status_code, 200)

    def test_read_is_idempotent_and_updates_web(self):
        url = f'/api/notifications/{self.notification.pk}/read/'
        self.assertEqual(self.client.get('/api/notifications/unread-count/').data['unread_count'], 1)
        for _ in range(2):
            response = self.client.post(url)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.data['is_read'])
        self.assertEqual(self.client.get('/api/notifications/unread-count/').data['unread_count'], 0)
        self.notification.refresh_from_db()
        self.assertTrue(self.notification.is_read)
        self.assertEqual(self.notification.email_status, Notification.EmailStatus.SKIPPED)
        self.client.force_login(self.user)
        self.assertContains(self.client.get('/notification/'), 'Pengingat')

    def test_web_read_is_visible_to_api(self):
        self.client.force_login(self.user)
        response = self.client.post(f'/notification/{self.notification.pk}/read/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.client.get(f'/api/notifications/{self.notification.pk}/').data['is_read'])

    def test_foreign_notification_cannot_be_read_or_changed(self):
        url = f'/api/notifications/{self.foreign.pk}/'
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url + 'read/').status_code, 404)
        self.foreign.refresh_from_db()
        self.assertFalse(self.foreign.is_read)

    def test_anonymous_or_invalid_token_cannot_access_actions(self):
        urls = [('/api/notifications/', 'get'), ('/api/notifications/unread-count/', 'get'),
                ('/api/notifications/refresh/', 'post'),
                (f'/api/notifications/{self.notification.pk}/read/', 'post')]
        for header in ('', 'Token invalid'):
            self.client.credentials(HTTP_AUTHORIZATION=header)
            for url, method in urls:
                with self.subTest(header=header, url=url):
                    self.assertEqual(getattr(self.client, method)(url).status_code, 401)

    def test_notifications_cannot_be_created_edited_or_deleted_freely(self):
        url = f'/api/notifications/{self.notification.pk}/'
        self.assertEqual(self.client.post('/api/notifications/', {'title': 'Fake'}, format='json').status_code, 405)
        self.assertEqual(self.client.patch(url, {'is_read': True, 'email_status': 'SENT'}, format='json').status_code, 405)
        self.assertEqual(self.client.delete(url).status_code, 405)

    @patch('notification.views.send_mail')
    def test_reminders_are_own_idempotent_and_do_not_send_email(self, send_mail):
        today = timezone.localdate()
        for owner in (self.user, self.other):
            FoodItem.objects.create(owner=owner, name='Roti', purchase_date=today,
                expiration_date=today + timedelta(days=3))
        response = self.client.post('/api/notifications/refresh/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['created'], 1)
        self.assertEqual(self.client.post('/api/notifications/refresh/').data['created'], 0)
        self.assertEqual(self.client.get('/api/notifications/').data['count'], 2)
        self.assertEqual(Notification.objects.filter(recipient=self.other).count(), 1)
        send_mail.assert_not_called()

    def test_session_writes_require_csrf(self):
        self.client.credentials()
        self.client.force_login(self.user)
        self.client.handler.enforce_csrf_checks = True
        response = self.client.post(f'/api/notifications/{self.notification.pk}/read/')
        self.assertEqual(response.status_code, 403)
