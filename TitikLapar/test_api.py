from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase, APIClient

from FoodItem.models import FoodItem
from Location.models import Location
from SharedPost.models import SharedPost
from notification.models import Notification
from userprofile.models import UserProfile


@override_settings(SHAREDPOST_WRITE_LIMIT=1000)
class ModuleAPITests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user('owner', 'owner@example.com', 'ApiTesting-827!')
        self.other = get_user_model().objects.create_user('other', 'other@example.com', 'ApiTesting-827!')
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        self.today = timezone.localdate()
        self.food = FoodItem.objects.create(owner=self.user, name='Apel', purchase_date=self.today,
            expiration_date=self.today + timedelta(days=3))
        self.location = Location.objects.create(owner=self.user, area_name='Beji', latitude='-6.361234', longitude='106.821234')
        self.foreign_location = Location.objects.create(owner=self.other, area_name='Privat', latitude='-6.400000', longitude='106.800000')
        self.foreign_food = FoodItem.objects.create(owner=self.other, name='Pisang', purchase_date=self.today,
            expiration_date=self.today + timedelta(days=5))

    def post_offer(self, food=None, location=None):
        return self.client.post('/api/posts/', {'food_item': (food or self.food).pk,
            'location': (location or self.location).pk, 'description': 'Ambil sore di gerbang utama.'}, format='json')

    def test_api_root_and_all_module_reads(self):
        for url in ('/api/', '/api/foods/', '/api/locations/', '/api/posts/',
                    '/api/notifications/', '/api/profile/'):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200, response.data)
                self.assertIn('application/json', response['Content-Type'])

    def test_anonymous_cannot_access_modules(self):
        self.client.credentials()
        for url in ('/api/', '/api/foods/', '/api/locations/', '/api/posts/', '/api/notifications/', '/api/profile/'):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 401)

    def test_private_api_responses_are_not_cached(self):
        for url in ('/api/profile/', '/api/foods/', '/api/locations/', '/api/posts/', '/api/notifications/',
                    f'/api/contacts/{self.user.pk}/'):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertIn('no-store', response['Cache-Control'])
                self.assertIn('private', response['Cache-Control'])

    def test_registration_login_logout_and_revocation(self):
        client = APIClient()
        response = client.post('/api/auth/register/', {'username': 'new-user', 'email': 'new@example.com',
            'password1': 'NewAccount-673!', 'password2': 'NewAccount-673!'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        user = get_user_model().objects.get(username='new-user')
        self.assertTrue(user.check_password('NewAccount-673!'))
        self.assertTrue(UserProfile.objects.filter(user=user).exists())
        response = client.post('/api/auth/login/', {'username': 'new-user', 'password': 'NewAccount-673!'}, format='json')
        self.assertEqual(response.status_code, 200)
        client.credentials(HTTP_AUTHORIZATION='Token ' + response.data['token'])
        self.assertEqual(client.get('/api/profile/').status_code, 200)
        self.assertEqual(client.post('/api/auth/logout/').status_code, 204)
        self.assertEqual(client.get('/api/profile/').status_code, 401)

    def test_invalid_auth_and_password_validation(self):
        client = APIClient()
        self.assertEqual(client.post('/api/auth/login/', {'username': 'owner', 'password': 'wrong'}, format='json').status_code, 401)
        self.assertEqual(client.post('/api/auth/register/', {'username': 'new', 'email': 'new@example.com',
            'password1': '123', 'password2': '123'}, format='json').status_code, 400)
        client.credentials(HTTP_AUTHORIZATION='Token invalid')
        self.assertEqual(client.get('/api/profile/').status_code, 401)

    def test_food_crud_and_json_status(self):
        response = self.client.post('/api/foods/', {'name': 'Roti', 'category': 'GRAIN', 'owner': self.other.pk}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        url = f"/api/foods/{response.data['id']}/"
        self.assertEqual(response.data['owner'], self.user.pk)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.patch(url, {'name': 'Roti tawar'}, format='json').data['name'], 'Roti tawar')
        self.assertEqual(self.client.post(url + 'status/', {'status': 'CONSUMED'}, format='json').status_code, 200)
        self.assertEqual(self.client.get(url).data['status'], 'CONSUMED')
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_food_dates_and_status_rules(self):
        self.assertEqual(self.client.post('/api/foods/', {'name': 'Invalid', 'purchase_date': str(self.today),
            'expiration_date': str(self.today - timedelta(days=1))}, format='json').status_code, 400)
        self.assertEqual(self.client.post(f'/api/foods/{self.food.pk}/status/', {'status': 'OFFERED'}, format='json').status_code, 409)
        self.assertEqual(self.client.post(f'/api/foods/{self.food.pk}/status/', {'status': 'INVALID'}, format='json').status_code, 400)

    def test_extending_expired_food_does_not_revive_offer(self):
        post_id = self.post_offer().data['id']
        FoodItem.objects.filter(pk=self.food.pk).update(
            purchase_date=self.today - timedelta(days=5), expiration_date=self.today - timedelta(days=1))
        response = self.client.patch(f'/api/foods/{self.food.pk}/',
            {'expiration_date': str(self.today + timedelta(days=5))}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.food.refresh_from_db()
        self.assertEqual(self.food.status, 'STORED')
        self.assertFalse(SharedPost.objects.get(pk=post_id).is_active)
        self.assertEqual(self.client.get('/api/posts/').data['count'], 0)

    def test_food_api_schedules_same_reminder_workflow_after_commit(self):
        with patch('FoodItem.views.send_pending_reminder_emails') as send_emails:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post('/api/foods/', {'name': 'Susu',
                    'expiration_date': str(self.today + timedelta(days=1))}, format='json')
            self.assertEqual(response.status_code, 201, response.data)
            reminder = Notification.objects.get(food_item_id=response.data['id'])
            self.assertEqual(reminder.recipient, self.user)
            self.assertEqual(reminder.reminder_days, 1)
            send_emails.assert_called_once()

    def test_notification_list_generates_reminders_like_web(self):
        response = self.client.get('/api/notifications/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(self.client.get('/api/notifications/').data['count'], 1)

    def test_food_name_sanitization_matches_web(self):
        response = self.client.post('/api/foods/', {'name': '<b>Apel</b>'}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['name'], 'Apel')
        self.assertEqual(self.client.post('/api/foods/', {'name': '<br>'}, format='json').status_code, 400)

    def test_consumed_or_expired_food_cannot_be_offered(self):
        for status, expiry in (('CONSUMED', self.today + timedelta(days=1)), ('STORED', self.today - timedelta(days=1))):
            FoodItem.objects.filter(pk=self.food.pk).update(status=status, expiration_date=expiry)
            self.assertEqual(self.post_offer().status_code, 400)
        self.assertFalse(SharedPost.objects.filter(food_item=self.food).exists())

    def test_web_and_api_share_status_and_cannot_reopen_completed_post(self):
        response = self.post_offer()
        post_id = response.data['id']
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/berbagi/').status_code, 200)
        self.assertEqual(self.client.post(f'/berbagi/{post_id}/complete/').status_code, 302)
        self.food.refresh_from_db()
        self.assertEqual(self.food.status, 'CONSUMED')
        url = f'/api/posts/{post_id}/'
        self.assertEqual(self.client.patch(url, {'is_active': True, 'description': 'Aktif kembali secara paksa.'}, format='json').status_code, 400)
        self.assertEqual(self.client.post(url + 'complete/').status_code, 400)
        self.assertFalse(SharedPost.objects.get(pk=post_id).is_active)

    def test_web_and_api_blank_dates_use_today(self):
        self.client.force_login(self.user)
        response = self.client.post('/fooditem/add/', {'name': 'Web food', 'category': 'FRUIT',
            'purchase_date': '', 'expiration_date': '', 'image_url': ''})
        self.assertEqual(response.status_code, 302)
        web_food = FoodItem.objects.get(name='Web food')
        for empty in ('', None):
            response = self.client.post('/api/foods/', {'name': 'API food', 'category': 'FRUIT',
                'purchase_date': empty, 'expiration_date': empty}, format='json')
            self.assertEqual(response.status_code, 201, response.data)
            self.assertEqual(response.data['purchase_date'], str(web_food.purchase_date))
            self.assertEqual(response.data['expiration_date'], str(web_food.expiration_date))

    def test_post_created_on_web_is_editable_on_api_and_storable_on_web(self):
        self.client.force_login(self.user)
        response = self.client.post('/berbagi/create/', {'food_item': self.food.pk,
            'location': self.location.pk, 'description': 'Ambil di gerbang kampus.'})
        self.assertEqual(response.status_code, 302)
        post = SharedPost.objects.get(food_item=self.food)
        url = f'/api/posts/{post.pk}/'
        self.assertEqual(self.client.get(url).data['food_name'], self.food.name)
        response = self.client.patch(url, {'description': 'Petunjuk baru dari mobile.'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertContains(self.client.get(f'/berbagi/{post.pk}/'), 'Petunjuk baru dari mobile.')
        response = self.client.post(f'/fooditem/{self.food.pk}/status/', {'status': 'STORED'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get('/api/posts/').data['count'], 0)
        self.assertFalse(self.client.get(url).data['is_active'])

    def test_closed_post_can_be_replaced_but_food_cannot_be_swapped(self):
        post_id = self.post_offer().data['id']
        self.assertEqual(self.client.post(f'/api/foods/{self.food.pk}/status/',
            {'status': 'STORED'}, format='json').status_code, 200)
        response = self.post_offer()
        self.assertEqual(response.status_code, 201, response.data)
        replacement_id = response.data['id']
        self.assertNotEqual(post_id, replacement_id)
        another_food = FoodItem.objects.create(owner=self.user, name='Other food',
            purchase_date=self.today, expiration_date=self.today + timedelta(days=2))
        response = self.client.patch(f'/api/posts/{replacement_id}/', {'food_item': another_food.pk}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(SharedPost.objects.get(pk=replacement_id).food_item_id, self.food.pk)
        self.assertEqual(SharedPost.objects.filter(food_item=self.food, is_active=True).count(), 1)

    def test_delete_food_cascades_posts_but_preserves_notification_history(self):
        self.post_offer()
        notification = Notification.objects.create(recipient=self.user, food_item=self.food,
            title='Pengingat', message='Riwayat tetap ada.')
        response = self.client.delete(f'/api/foods/{self.food.pk}/')
        self.assertEqual(response.status_code, 204)
        self.assertFalse(SharedPost.objects.filter(food_item_id=self.food.pk).exists())
        notification.refresh_from_db()
        self.assertIsNone(notification.food_item_id)
        self.assertEqual(self.client.get('/api/notifications/').data['count'], 1)

    def test_pins_reject_legacy_cross_owner_locations_like_web_map(self):
        post_id = self.post_offer().data['id']
        SharedPost.objects.filter(pk=post_id).update(location=self.foreign_location)
        self.assertEqual(self.client.get('/api/locations/pins/').data, [])

    def test_pin_distances_use_same_default_location_as_web(self):
        self.post_offer()
        UserProfile.objects.create(user=self.user, default_location=self.location)
        from Location.services import distance_km
        from SharedPost.services import public_coordinates
        lat, lon = public_coordinates(self.location)
        expected = round(distance_km(self.location.latitude, self.location.longitude, lat, lon), 2)
        self.assertEqual(self.client.get('/api/locations/pins/').data[0]['distance_km'], expected)

    def test_inactive_account_token_and_login_are_rejected(self):
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        self.assertEqual(self.client.get('/api/foods/').status_code, 401)
        client = APIClient()
        response = client.post('/api/auth/login/', {'username': 'owner', 'password': 'ApiTesting-827!'}, format='json')
        self.assertEqual(response.status_code, 401)

    @override_settings(SHAREDPOST_WRITE_LIMIT=1)
    def test_web_and_api_share_write_quota(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.post('/berbagi/create/', {}).status_code, 200)
        self.assertEqual(self.post_offer().status_code, 429)

    def test_food_ordering(self):
        FoodItem.objects.create(owner=self.user, name='Besok', purchase_date=self.today,
            expiration_date=self.today + timedelta(days=1))
        response = self.client.get('/api/foods/?ordering=expiration_date')
        self.assertEqual([f['name'] for f in response.data['results']], ['Besok', 'Apel'])

    def test_private_food_and_location_ownership(self):
        self.assertEqual(self.client.get('/api/foods/').data['count'], 1)
        self.assertEqual(self.client.get('/api/locations/').data['count'], 1)
        for url in (f'/api/foods/{self.foreign_food.pk}/', f'/api/locations/{self.foreign_location.pk}/'):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)
                self.assertEqual(self.client.patch(url, {'name': 'Changed'}, format='json').status_code, 404)
                self.assertEqual(self.client.delete(url).status_code, 404)

    def test_location_crud_and_default(self):
        response = self.client.post('/api/locations/', {'area_name': 'Kampus', 'latitude': '-6.36', 'longitude': '106.82'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        url = f"/api/locations/{response.data['id']}/"
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.patch(url, {'area_name': 'Kampus UI'}, format='json').status_code, 200)
        self.assertEqual(self.client.post(url + 'set_default/').status_code, 200)
        self.assertEqual(self.client.get('/api/profile/').data['default_location'], response.data['id'])
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertIsNone(self.client.get('/api/profile/').data['default_location'])

    def test_location_range_validation(self):
        response = self.client.post('/api/locations/', {'area_name': 'Invalid', 'latitude': 91, 'longitude': 181}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_post_create_update_complete(self):
        response = self.post_offer()
        self.assertEqual(response.status_code, 201, response.data)
        url = f"/api/posts/{response.data['id']}/"
        self.food.refresh_from_db()
        self.assertEqual(self.food.status, 'OFFERED')
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.patch(url, {'description': 'Ambil pagi di gerbang utama.'}, format='json').status_code, 200)
        self.assertEqual(self.client.post(url + 'complete/').status_code, 200)
        self.food.refresh_from_db()
        self.assertEqual(self.food.status, 'CONSUMED')
        self.assertFalse(SharedPost.objects.get(pk=response.data['id']).is_active)
        self.assertEqual(self.client.get('/api/posts/').data['count'], 0)

    def test_post_delete_restores_stored(self):
        response = self.post_offer()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.client.delete(f"/api/posts/{response.data['id']}/").status_code, 204)
        self.food.refresh_from_db()
        self.assertEqual(self.food.status, 'STORED')

    def test_post_rejects_duplicate_foreign_food_and_location(self):
        self.assertEqual(self.post_offer(food=self.foreign_food).status_code, 400)
        self.assertEqual(self.post_offer(location=self.foreign_location).status_code, 400)
        self.assertEqual(self.post_offer().status_code, 201)
        self.assertEqual(self.post_offer().status_code, 400)

    def test_post_is_readable_but_not_mutable_by_other_user(self):
        response = self.post_offer()
        url = f"/api/posts/{response.data['id']}/"
        self.client.force_authenticate(user=self.other)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.patch(url, {'description': 'Tidak boleh diubah.'}, format='json').status_code, 404)
        self.assertEqual(self.client.post(url + 'complete/').status_code, 404)
        self.assertEqual(self.client.delete(url).status_code, 404)
        self.assertEqual(self.client.get('/api/posts/?mine=1').data['count'], 0)

    def test_expired_offer_hidden_and_food_edit_deactivates_offer(self):
        post_id = self.post_offer().data['id']
        FoodItem.objects.filter(pk=self.food.pk).update(purchase_date=self.today - timedelta(days=5))
        response = self.client.patch(f'/api/foods/{self.food.pk}/', {'expiration_date': str(self.today - timedelta(days=1))}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(SharedPost.objects.get(pk=post_id).is_active)
        self.client.force_authenticate(user=self.other)
        self.assertEqual(self.client.get(f'/api/posts/{post_id}/').status_code, 404)

    def test_used_location_is_protected(self):
        self.post_offer()
        url = f'/api/locations/{self.location.pk}/'
        self.assertEqual(self.client.patch(url, {'area_name': 'Moved'}, format='json').status_code, 409)
        self.assertEqual(self.client.delete(url).status_code, 409)

    def test_map_only_exposes_approximate_shared_locations(self):
        self.post_offer()
        self.client.force_authenticate(user=self.other)
        response = self.client.get('/api/locations/pins/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['latitude'], '-6.361')
        self.assertEqual(response.data[0]['longitude'], '106.821')

    def test_profile_update_and_contact_privacy(self):
        response = self.client.patch('/api/profile/', {'email': 'changed@example.com', 'whatsapp_number': '628123456789',
            'line_id': 'owner-line', 'default_location': self.location.pk}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'changed@example.com')
        self.assertEqual(self.client.patch('/api/profile/', {'default_location': self.foreign_location.pk}, format='json').status_code, 400)
        response = self.client.get(f'/api/contacts/{self.user.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.data), {'username', 'whatsapp_number', 'line_id'})
        self.assertEqual(response.data['line_id'], 'owner-line')

    def test_profile_phone_validation(self):
        self.assertEqual(self.client.patch('/api/profile/', {'whatsapp_number': '+62 bad'}, format='json').status_code, 400)

    def test_notifications_refresh_read_and_ownership(self):
        response = self.client.post('/api/notifications/refresh/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['created'], 1)
        self.assertEqual(self.client.post('/api/notifications/refresh/').data['created'], 0)
        response = self.client.get('/api/notifications/')
        self.assertEqual(response.data['count'], 1)
        pk = response.data['results'][0]['id']
        self.assertNotIn('last_email_error', response.data['results'][0])
        self.assertEqual(self.client.get(f'/api/notifications/{pk}/').status_code, 200)
        self.assertEqual(self.client.get('/api/notifications/unread-count/').data['unread_count'], 1)
        self.assertEqual(self.client.post(f'/api/notifications/{pk}/read/').status_code, 200)
        self.assertEqual(self.client.get('/api/notifications/unread-count/').data['unread_count'], 0)
        self.client.force_authenticate(user=self.other)
        self.assertEqual(self.client.get('/api/notifications/').data['count'], 0)
        self.assertEqual(self.client.get(f'/api/notifications/{pk}/').status_code, 404)
        self.assertEqual(self.client.post(f'/api/notifications/{pk}/read/').status_code, 404)

    def test_account_delete_requires_password_and_confirmation(self):
        self.assertEqual(self.client.delete('/api/profile/', {'password': 'bad', 'confirm': True}, format='json').status_code, 400)
        self.assertEqual(self.client.delete('/api/profile/', {'password': 'ApiTesting-827!', 'confirm': False}, format='json').status_code, 400)
        self.assertEqual(self.client.delete('/api/profile/', {'password': 'ApiTesting-827!', 'confirm': True}, format='json').status_code, 204)
        self.assertFalse(get_user_model().objects.filter(pk=self.user.pk).exists())
        self.assertFalse(Token.objects.filter(key=self.token.key).exists())

    def test_token_writes_work_without_csrf_but_session_writes_require_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post('/api/foods/', {'name': 'Test'}, format='json').status_code, 403)
        client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        self.assertEqual(client.post('/api/foods/', {'name': 'Test'}, format='json').status_code, 201)

    @override_settings(SHAREDPOST_WRITE_LIMIT=1)
    def test_sharedpost_api_respects_write_quota(self):
        self.assertEqual(self.post_offer().status_code, 201)
        response = self.post_offer()
        self.assertEqual(response.status_code, 429)
        self.assertIn('Retry-After', response)
