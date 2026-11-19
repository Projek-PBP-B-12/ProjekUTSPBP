from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient, APITestCase

from FoodItem.models import FoodItem
from SharedPost.models import SharedPost
from userprofile.models import UserProfile
from .models import Location


class LocationAPITests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('map-owner')
        self.other = get_user_model().objects.create_user('map-other')
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        self.location = Location.objects.create(owner=self.user, area_name='Kampus',
            latitude='-6.361234', longitude='106.821234')
        self.foreign_location = Location.objects.create(owner=self.other, area_name='Private area',
            latitude='-6.371234', longitude='106.831234')

    def offer(self, **overrides):
        food = FoodItem.objects.create(owner=self.user, name='Apel', status='OFFERED',
            purchase_date=timezone.localdate(), expiration_date=timezone.localdate() + timedelta(days=3))
        data = {'food_item': food, 'location': self.location,
                'description': 'Ambil di gerbang utama.', 'is_active': True}
        data.update(overrides)
        return SharedPost.objects.create(**data)

    def test_location_crud_and_owner_assigned_by_server(self):
        response = self.client.post('/api/locations/', {'area_name': 'Kos',
            'latitude': '-6.36', 'longitude': '106.82', 'owner': self.other.pk}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['owner'], self.user.pk)
        url = f"/api/locations/{response.data['id']}/"
        self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.put(url, {'area_name': 'Kos baru', 'latitude': '-6.37',
            'longitude': '106.83'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        response = self.client.patch(url, {'area_name': 'Kos utara'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['area_name'], 'Kos utara')
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_private_locations_are_owner_only(self):
        response = self.client.get('/api/locations/')
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], self.location.pk)
        url = f'/api/locations/{self.foreign_location.pk}/'
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.patch(url, {'area_name': 'Hijacked'}, format='json').status_code, 404)
        self.assertEqual(self.client.delete(url).status_code, 404)
        self.assertEqual(self.client.post(url + 'set_default/').status_code, 404)
        self.foreign_location.refresh_from_db()
        self.assertEqual(self.foreign_location.owner_id, self.other.pk)

    def test_coordinates_and_empty_area_are_validated(self):
        invalid = ({'latitude': '91'}, {'latitude': '-91'}, {'longitude': '181'},
                   {'longitude': '-181'}, {'latitude': 'NaN'}, {'latitude': '-6.1234567'},
                   {'area_name': ''}, {'latitude': None})
        for fields in invalid:
            data = {'area_name': 'Invalid', 'latitude': '-6.36', 'longitude': '106.82'}
            data.update(fields)
            with self.subTest(fields=fields):
                self.assertEqual(self.client.post('/api/locations/', data, format='json').status_code, 400)

    def test_set_default_uses_same_profile_and_web_map_center(self):
        response = self.client.post(f'/api/locations/{self.location.pk}/set_default/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['default_location'], self.location.pk)
        self.assertEqual(UserProfile.objects.get(user=self.user).default_location_id, self.location.pk)
        self.client.force_login(self.user)
        response = self.client.get(reverse('Location:map'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['map_center']['label'], self.location.area_name)
        self.assertTrue(response.context['map_center']['is_default'])

    def test_deleting_unused_default_location_clears_profile_reference(self):
        UserProfile.objects.create(user=self.user, default_location=self.location)
        self.assertEqual(self.client.delete(f'/api/locations/{self.location.pk}/').status_code, 204)
        self.assertIsNone(UserProfile.objects.get(user=self.user).default_location_id)

    def test_location_referenced_by_offer_cannot_be_changed_or_deleted(self):
        post = self.offer()
        url = f'/api/locations/{self.location.pk}/'
        for active in (True, False):
            SharedPost.objects.filter(pk=post.pk).update(is_active=active)
            with self.subTest(active=active):
                self.assertEqual(self.client.patch(url, {'area_name': 'Moved'}, format='json').status_code, 409)
                self.assertEqual(self.client.delete(url).status_code, 409)
        self.location.refresh_from_db()
        self.assertEqual(self.location.area_name, 'Kampus')

    def test_api_pins_exactly_match_web_pins_and_distances(self):
        self.offer()
        UserProfile.objects.create(user=self.user, default_location=self.location)
        self.client.force_login(self.user)
        web = self.client.get(reverse('Location:map'))
        response = self.client.get('/api/locations/pins/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, web.context['pins'])
        self.assertEqual(response.data[0]['latitude'], '-6.361')
        self.assertEqual(response.data[0]['longitude'], '106.821')
        self.assertIsNotNone(response.data[0]['distance_km'])

    def test_pins_hide_private_and_mismatched_legacy_locations(self):
        post = self.offer(location=self.foreign_location)
        self.assertEqual(self.client.get('/api/locations/pins/').data, [])
        SharedPost.objects.filter(pk=post.pk).update(location=self.location)
        response = self.client.get('/api/locations/pins/')
        self.assertEqual(len(response.data), 1)
        self.assertNotIn('Private area', str(response.data))
        self.assertIsNone(response.data[0]['distance_km'])

    def test_unavailable_offers_do_not_appear_on_map(self):
        post = self.offer()
        food = post.food_item
        today = timezone.localdate()
        scenarios = (
            {'post_active': False, 'food_status': 'OFFERED', 'expiry': today, 'owner_active': True},
            {'post_active': True, 'food_status': 'CONSUMED', 'expiry': today, 'owner_active': True},
            {'post_active': True, 'food_status': 'OFFERED', 'expiry': today - timedelta(days=1), 'owner_active': True},
            {'post_active': True, 'food_status': 'OFFERED', 'expiry': today, 'owner_active': False},
        )
        self.client.force_authenticate(user=self.other)
        for state in scenarios:
            with self.subTest(state=state):
                SharedPost.objects.filter(pk=post.pk).update(is_active=state['post_active'])
                FoodItem.objects.filter(pk=food.pk).update(status=state['food_status'], expiration_date=state['expiry'])
                get_user_model().objects.filter(pk=self.user.pk).update(is_active=state['owner_active'])
                self.assertEqual(self.client.get('/api/locations/pins/').data, [])

    def test_authentication_and_session_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        self.assertEqual(client.get('/api/locations/').status_code, 401)
        self.assertEqual(client.get('/api/locations/pins/').status_code, 401)
        client.credentials(HTTP_AUTHORIZATION='Token invalid')
        self.assertEqual(client.get('/api/locations/pins/').status_code, 401)
        client.credentials()
        client.force_login(self.user)
        url = f'/api/locations/{self.location.pk}/set_default/'
        self.assertEqual(client.post(url).status_code, 403)
        client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        self.assertEqual(client.post(url).status_code, 200)

    def test_search_and_private_cache_headers(self):
        self.assertEqual(self.client.get('/api/locations/?search=Kampus').data['count'], 1)
        self.assertEqual(self.client.get('/api/locations/?search=Private').data['count'], 0)
        for url in ('/api/locations/', '/api/locations/pins/', f'/api/locations/{self.location.pk}/'):
            self.assertIn('no-store', self.client.get(url)['Cache-Control'])

    def test_location_created_on_web_is_editable_through_api(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('Location:create_location'),
            {'area_name': 'Dari web', 'latitude': '-6.38', 'longitude': '106.84'})
        self.assertEqual(response.status_code, 201)
        pk = response.json()['id']
        response = self.client.patch(f'/api/locations/{pk}/', {'area_name': 'Diubah mobile'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Location.objects.get(pk=pk).area_name, 'Diubah mobile')
