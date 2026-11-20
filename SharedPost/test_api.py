from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from FoodItem.models import FoodItem
from Location.models import Location
from .models import SharedPost


@override_settings(SHAREDPOST_WRITE_LIMIT=1000)
class SharedPostAPITests(APITestCase):
    def setUp(self):
        cache.clear()
        self.owner = get_user_model().objects.create_user('donor')
        self.other = get_user_model().objects.create_user('visitor')
        token = Token.objects.create(user=self.owner)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)
        today = timezone.localdate()
        self.food = FoodItem.objects.create(owner=self.owner, name='Apel',
            purchase_date=today, expiration_date=today + timedelta(days=3))
        self.location = Location.objects.create(owner=self.owner, area_name='Beji',
            latitude='-6.361234', longitude='106.821234')
        self.foreign_location = Location.objects.create(owner=self.other, area_name='Privat',
            latitude='-6.400000', longitude='106.800000')

    def create_offer(self, **overrides):
        data = {'food_item': self.food.pk, 'location': self.location.pk,
                'description': 'Ambil sore di gerbang utama.'}
        data.update(overrides)
        return self.client.post('/api/posts/', data, format='json')

    def test_create_read_update_complete(self):
        response = self.create_offer()
        self.assertEqual(response.status_code, 201, response.data)
        url = f"/api/posts/{response.data['id']}/"
        self.food.refresh_from_db()
        self.assertEqual(self.food.status, 'OFFERED')
        self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.patch(url, {'description': '  Ambil pagi di gerbang.  '}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['description'], 'Ambil pagi di gerbang.')
        self.assertEqual(self.client.post(url + 'complete/').status_code, 200)
        self.food.refresh_from_db()
        self.assertEqual(self.food.status, 'CONSUMED')
        self.assertFalse(self.client.get(url).data['is_active'])
        self.assertEqual(self.client.get('/api/posts/').data['count'], 0)
        self.assertEqual(self.client.patch(url, {'is_active': True}, format='json').status_code, 400)
        self.assertEqual(self.client.post(url + 'complete/').status_code, 400)

    def test_delete_restores_stored_and_allows_new_offer(self):
        post_id = self.create_offer().data['id']
        self.assertEqual(self.client.delete(f'/api/posts/{post_id}/').status_code, 204)
        self.food.refresh_from_db()
        self.assertEqual(self.food.status, 'STORED')
        self.assertFalse(SharedPost.objects.filter(pk=post_id).exists())
        self.assertEqual(self.create_offer().status_code, 201)

    def test_other_user_can_read_available_offer_but_cannot_modify_it(self):
        post_id = self.create_offer().data['id']
        url = f'/api/posts/{post_id}/'
        self.client.force_authenticate(user=self.other)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.patch(url, {'description': 'Tidak boleh mengubah.'}, format='json').status_code, 404)
        self.assertEqual(self.client.post(url + 'complete/').status_code, 404)
        self.assertEqual(self.client.delete(url).status_code, 404)
        self.assertEqual(self.client.get('/api/posts/?mine=1').data['count'], 0)

    def test_foreign_food_or_location_and_duplicate_offer_rejected(self):
        self.assertEqual(self.create_offer(location=self.foreign_location.pk).status_code, 400)
        FoodItem.objects.filter(pk=self.food.pk).update(owner=self.other)
        self.assertEqual(self.create_offer().status_code, 400)
        FoodItem.objects.filter(pk=self.food.pk).update(owner=self.owner)
        self.assertEqual(self.create_offer().status_code, 201)
        self.assertEqual(self.create_offer().status_code, 400)

    def test_expired_or_consumed_food_and_short_description_rejected(self):
        self.assertEqual(self.create_offer(description='short').status_code, 400)
        FoodItem.objects.filter(pk=self.food.pk).update(status='CONSUMED')
        self.assertEqual(self.create_offer().status_code, 400)
        FoodItem.objects.filter(pk=self.food.pk).update(status='STORED',
            expiration_date=timezone.localdate() - timedelta(days=1))
        self.assertEqual(self.create_offer().status_code, 400)

    def test_unavailable_offer_hidden_from_visitors_but_visible_to_owner(self):
        post_id = self.create_offer().data['id']
        SharedPost.objects.filter(pk=post_id).update(is_active=False)
        url = f'/api/posts/{post_id}/'
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_authenticate(user=self.other)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get('/api/posts/').data['count'], 0)

    def test_food_cannot_be_replaced_on_edit(self):
        post_id = self.create_offer().data['id']
        food = FoodItem.objects.create(owner=self.owner, name='Roti',
            purchase_date=timezone.localdate(), expiration_date=timezone.localdate())
        response = self.client.patch(f'/api/posts/{post_id}/', {'food_item': food.pk}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(SharedPost.objects.get(pk=post_id).food_item_id, self.food.pk)

    def test_web_and_api_share_same_records_and_status(self):
        self.client.force_login(self.owner)
        response = self.client.post('/berbagi/create/', {'food_item': self.food.pk,
            'location': self.location.pk, 'description': 'Petunjuk dari website.'})
        self.assertEqual(response.status_code, 302)
        post = SharedPost.objects.get(food_item=self.food)
        self.assertEqual(self.client.get(f'/api/posts/{post.pk}/').data['description'], 'Petunjuk dari website.')
        self.assertEqual(self.client.post(f'/api/posts/{post.pk}/complete/').status_code, 200)
        self.assertContains(self.client.get(f'/berbagi/{post.pk}/'), self.food.name)
        self.food.refresh_from_db()
        self.assertEqual(self.food.status, 'CONSUMED')

    def test_anonymous_invalid_token_and_csrf_rejected(self):
        self.client.credentials()
        self.assertEqual(self.client.get('/api/posts/').status_code, 401)
        self.assertEqual(self.create_offer().status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION='Token invalid')
        self.assertEqual(self.client.get('/api/posts/').status_code, 401)
        self.client.credentials()
        self.client.force_login(self.owner)
        self.client.handler.enforce_csrf_checks = True
        self.assertEqual(self.create_offer().status_code, 403)

    def test_filter_ordering_and_private_cache_policy(self):
        self.create_offer()
        response = self.client.get('/api/posts/?search=Apel&mine=1&ordering=food_item__expiration_date')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(self.client.get('/api/posts/?search=TidakAda').data['count'], 0)

    @override_settings(SHAREDPOST_WRITE_LIMIT=1)
    def test_write_quota_shared_with_web(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post('/berbagi/create/', {}).status_code, 200)
        response = self.create_offer()
        self.assertEqual(response.status_code, 429)
        self.assertIn('Retry-After', response)
