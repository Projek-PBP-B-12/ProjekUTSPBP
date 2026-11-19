from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient, APITestCase

from Location.models import Location
from SharedPost.models import SharedPost
from notification.models import Notification
from .models import FoodItem


class FoodItemAPITests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('food-owner')
        self.other = get_user_model().objects.create_user('food-other')
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        self.today = timezone.localdate()
        self.food = FoodItem.objects.create(owner=self.user, name='Apel', category='FRUIT',
            purchase_date=self.today, expiration_date=self.today + timedelta(days=3))
        self.foreign = FoodItem.objects.create(owner=self.other, name='Privat',
            purchase_date=self.today, expiration_date=self.today + timedelta(days=5))

    def make_offer(self):
        location = Location.objects.create(owner=self.user, area_name='Beji',
            latitude='-6.36', longitude='106.82')
        post = SharedPost.objects.create(food_item=self.food, location=location,
            description='Ambil sore di gerbang utama.')
        FoodItem.objects.filter(pk=self.food.pk).update(status='OFFERED')
        return post

    def test_create_retrieve_put_patch_delete(self):
        response = self.client.post('/api/foods/', {'name': 'Roti', 'category': 'GRAIN'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        url = f"/api/foods/{response.data['id']}/"
        self.assertEqual(self.client.get(url).data['owner'], self.user.pk)
        response = self.client.put(url, {'name': 'Roti tawar', 'category': 'GRAIN',
            'purchase_date': str(self.today), 'expiration_date': str(self.today + timedelta(days=2)),
            'image_url': ''}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['days_until_expiration'], 2)
        self.assertFalse(response.data['is_expired'])
        self.assertEqual(self.client.patch(url, {'name': 'Roti gandum'}, format='json').data['name'], 'Roti gandum')
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_foreign_food_is_private_for_all_mutations(self):
        response = self.client.get('/api/foods/')
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], self.food.pk)
        url = f'/api/foods/{self.foreign.pk}/'
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.patch(url, {'name': 'Hijacked'}, format='json').status_code, 404)
        self.assertEqual(self.client.delete(url).status_code, 404)
        self.assertEqual(self.client.post(url + 'status/', {'status': 'CONSUMED'}, format='json').status_code, 404)
        self.foreign.refresh_from_db()
        self.assertEqual(self.foreign.status, 'STORED')

    def test_missing_blank_and_null_dates_default_to_today(self):
        for fields in ({}, {'purchase_date': '', 'expiration_date': ''},
                       {'purchase_date': None, 'expiration_date': None}):
            with self.subTest(fields=fields):
                response = self.client.post('/api/foods/', {'name': 'Makanan', **fields}, format='json')
                self.assertEqual(response.status_code, 201, response.data)
                self.assertEqual(response.data['purchase_date'], str(self.today))
                self.assertEqual(response.data['expiration_date'], str(self.today))

    def test_invalid_dates_name_category_and_image_are_rejected(self):
        cases = ({'purchase_date': str(self.today), 'expiration_date': str(self.today - timedelta(days=1))},
                 {'expiration_date': 'not-a-date'}, {'name': '<br>'}, {'category': 'INVALID'},
                 {'image_url': 'ftp://example.com/image.jpg'})
        for fields in cases:
            with self.subTest(fields=fields):
                response = self.client.post('/api/foods/', {'name': 'Valid', **fields}, format='json')
                self.assertEqual(response.status_code, 400, response.data)
        response = self.client.post('/api/foods/', {'name': '<b>Apel</b>'}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['name'], 'Apel')

    def test_owner_status_and_derived_fields_cannot_be_forged(self):
        response = self.client.post('/api/foods/', {'name': 'Safe', 'owner': self.other.pk,
            'status': 'OFFERED', 'days_until_expiration': 999, 'is_expired': True}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['owner'], self.user.pk)
        self.assertEqual(response.data['status'], 'STORED')
        self.assertEqual(response.data['days_until_expiration'], 0)
        self.assertFalse(response.data['is_expired'])

    def test_search_ordering_and_private_cache(self):
        FoodItem.objects.create(owner=self.user, name='Besok', purchase_date=self.today,
            expiration_date=self.today + timedelta(days=1))
        response = self.client.get('/api/foods/?ordering=expiration_date')
        self.assertEqual([food['name'] for food in response.data['results']], ['Besok', 'Apel'])
        self.assertEqual(self.client.get('/api/foods/?search=Apel').data['count'], 1)
        self.assertEqual(self.client.get('/api/foods/?search=Privat').data['count'], 0)
        self.assertIn('no-store', response['Cache-Control'])

    def test_stored_and_consumed_close_active_offer(self):
        for status in ('STORED', 'CONSUMED'):
            post = self.make_offer()
            response = self.client.post(f'/api/foods/{self.food.pk}/status/', {'status': status}, format='json')
            self.assertEqual(response.status_code, 200, response.data)
            self.food.refresh_from_db()
            post.refresh_from_db()
            self.assertEqual(self.food.status, status)
            self.assertFalse(post.is_active)

    def test_offered_requires_available_food_and_active_offer(self):
        url = f'/api/foods/{self.food.pk}/status/'
        self.assertEqual(self.client.post(url, {'status': 'OFFERED'}, format='json').status_code, 409)
        self.make_offer()
        self.assertEqual(self.client.post(url, {'status': 'OFFERED'}, format='json').status_code, 200)
        FoodItem.objects.filter(pk=self.food.pk).update(expiration_date=self.today - timedelta(days=1))
        self.assertEqual(self.client.post(url, {'status': 'OFFERED'}, format='json').status_code, 409)
        self.assertEqual(self.client.post(url, {'status': 'INVALID'}, format='json').status_code, 400)

    def test_expiring_food_and_extending_expired_food_close_old_offers(self):
        url = f'/api/foods/{self.food.pk}/'
        for was_expired in (False, True):
            post = self.make_offer()
            FoodItem.objects.filter(pk=self.food.pk).update(
                purchase_date=self.today - timedelta(days=5),
                expiration_date=self.today - timedelta(days=1) if was_expired else self.today + timedelta(days=3))
            new_expiry = self.today + timedelta(days=5) if was_expired else self.today - timedelta(days=1)
            response = self.client.patch(url, {'expiration_date': str(new_expiry)}, format='json')
            self.assertEqual(response.status_code, 200, response.data)
            self.food.refresh_from_db()
            post.refresh_from_db()
            self.assertEqual(self.food.status, 'STORED')
            self.assertFalse(post.is_active)

    def test_delete_cascades_offer_but_preserves_notification_history(self):
        self.make_offer()
        notification = Notification.objects.create(recipient=self.user, food_item=self.food,
            title='Pengingat', message='Riwayat tersimpan.')
        self.assertEqual(self.client.delete(f'/api/foods/{self.food.pk}/').status_code, 204)
        self.assertFalse(SharedPost.objects.filter(food_item_id=self.food.pk).exists())
        notification.refresh_from_db()
        self.assertIsNone(notification.food_item_id)
        self.assertTrue(FoodItem.objects.filter(pk=self.foreign.pk).exists())

    def test_reminder_workflow_runs_only_after_successful_commit(self):
        with patch('FoodItem.views.send_pending_reminder_emails') as send_emails:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post('/api/foods/', {'name': 'Susu',
                    'expiration_date': str(self.today + timedelta(days=1))}, format='json')
                self.assertFalse(Notification.objects.filter(food_item_id=response.data['id']).exists())
                send_emails.assert_not_called()
            self.assertEqual(response.status_code, 201)
            notification = Notification.objects.get(food_item_id=response.data['id'])
            self.assertEqual(notification.recipient_id, self.user.pk)
            self.assertEqual(notification.reminder_days, 1)
            send_emails.assert_called_once()

    def test_web_create_api_edit_and_web_status_share_same_data(self):
        self.client.force_login(self.user)
        response = self.client.post('/fooditem/add/', {'name': 'Dari web', 'category': 'FRUIT',
            'purchase_date': '', 'expiration_date': '', 'image_url': ''})
        self.assertEqual(response.status_code, 302)
        food = FoodItem.objects.get(name='Dari web')
        url = f'/api/foods/{food.pk}/'
        self.assertEqual(self.client.patch(url, {'name': 'Dari mobile'}, format='json').status_code, 200)
        self.assertContains(self.client.get('/fooditem/makananku/'), 'Dari mobile')
        self.assertEqual(self.client.post(f'/fooditem/{food.pk}/status/', {'status': 'CONSUMED'}).status_code, 302)
        self.assertEqual(self.client.get(url).data['status'], 'CONSUMED')

    def test_authentication_and_inactive_accounts(self):
        client = APIClient()
        for header in ('', 'Token invalid'):
            client.credentials(HTTP_AUTHORIZATION=header)
            self.assertEqual(client.get('/api/foods/').status_code, 401)
            self.assertEqual(client.post('/api/foods/', {'name': 'No'}, format='json').status_code, 401)
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        self.assertEqual(self.client.get('/api/foods/').status_code, 401)

    def test_session_mutations_need_csrf_while_token_mutations_work(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.user)
        url = f'/api/foods/{self.food.pk}/'
        self.assertEqual(client.patch(url, {'name': 'Blocked'}, format='json').status_code, 403)
        client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        self.assertEqual(client.patch(url, {'name': 'Allowed'}, format='json').status_code, 200)
