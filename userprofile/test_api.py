from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient, APITestCase

from Location.models import Location
from .models import UserProfile


class UserProfileAPITests(APITestCase):
    password = 'Q7!mango-river-planet'

    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(
            'profile-owner', 'owner@example.com', self.password)
        self.other = get_user_model().objects.create_user(
            'profile-other', 'private@example.com', self.password)
        self.profile = UserProfile.objects.create(user=self.user)
        UserProfile.objects.create(user=self.other, whatsapp_number='628123456789', line_id='other.line')
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        self.location = Location.objects.create(owner=self.user, area_name='Kampus',
            latitude='-6.36', longitude='106.82')
        self.foreign_location = Location.objects.create(owner=self.other, area_name='Privat',
            latitude='-6.37', longitude='106.83')

    def register_data(self, **overrides):
        data = {'username': 'new-member', 'email': 'new@example.com',
                'password1': self.password, 'password2': self.password}
        data.update(overrides)
        return data

    def test_registration_creates_profile_and_hashes_password(self):
        response = APIClient().post('/api/auth/register/', self.register_data(), format='json')
        self.assertEqual(response.status_code, 201, response.data)
        user = get_user_model().objects.get(username='new-member')
        self.assertTrue(user.check_password(self.password))
        self.assertNotEqual(user.password, self.password)
        self.assertTrue(UserProfile.objects.filter(user=user).exists())
        self.assertNotIn('password', response.data)

    def test_registration_uses_web_validation(self):
        client = APIClient()
        invalid = (
            {'username': self.user.username},
            {'password1': '123', 'password2': '123'},
            {'password2': 'different'},
            {'email': 'not-an-email'},
        )
        for fields in invalid:
            with self.subTest(fields=fields):
                response = client.post('/api/auth/register/', self.register_data(**fields), format='json')
                self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(get_user_model().objects.filter(username='new-member').exists())

    def test_login_token_and_logout_revocation(self):
        client = APIClient()
        response = client.post('/api/auth/login/',
            {'username': self.user.username, 'password': self.password}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['user_id'], self.user.pk)
        client.credentials(HTTP_AUTHORIZATION='Token ' + response.data['token'])
        self.assertEqual(client.get('/api/profile/').status_code, 200)
        self.assertEqual(client.post('/api/auth/logout/').status_code, 204)
        self.assertEqual(client.get('/api/profile/').status_code, 401)
        self.assertFalse(Token.objects.filter(user=self.user).exists())

    def test_login_rejects_wrong_password_and_inactive_account(self):
        client = APIClient()
        response = client.post('/api/auth/login/',
            {'username': self.user.username, 'password': 'wrong'}, format='json')
        self.assertEqual(response.status_code, 401)
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        response = client.post('/api/auth/login/',
            {'username': self.user.username, 'password': self.password}, format='json')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.client.get('/api/profile/').status_code, 401)

    def test_anonymous_and_invalid_tokens_are_rejected(self):
        client = APIClient()
        for header in ('', 'Token invalid'):
            client.credentials(HTTP_AUTHORIZATION=header)
            for url, method in (('/api/profile/', 'get'), ('/api/profile/', 'patch'),
                                ('/api/profile/', 'delete'), ('/api/auth/logout/', 'post'),
                                (f'/api/contacts/{self.other.pk}/', 'get')):
                with self.subTest(header=header, url=url, method=method):
                    self.assertEqual(getattr(client, method)(url).status_code, 401)

    def test_update_profile_and_email_is_visible_on_web(self):
        response = self.client.patch('/api/profile/', {
            'email': 'changed@example.com', 'whatsapp_number': '628987654321',
            'line_id': 'owner.line', 'default_location': self.location.pk,
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.user.email, 'changed@example.com')
        self.assertEqual(self.profile.default_location_id, self.location.pk)
        self.client.force_login(self.user)
        self.assertContains(self.client.get('/accounts/profile/'), 'owner.line')
        self.assertIn('no-store', response['Cache-Control'])

    def test_foreign_location_invalid_phone_and_invalid_email_rejected(self):
        for data in ({'default_location': self.foreign_location.pk},
                     {'whatsapp_number': '+62 invalid'}, {'email': 'invalid'}):
            with self.subTest(data=data):
                self.assertEqual(self.client.patch('/api/profile/', data, format='json').status_code, 400)
        self.profile.refresh_from_db()
        self.assertIsNone(self.profile.default_location_id)
        self.other.refresh_from_db()
        self.assertEqual(self.other.email, 'private@example.com')

    def test_profile_cannot_change_identity_privileges_or_other_account(self):
        response = self.client.patch('/api/profile/', {
            'user': self.other.pk, 'username': 'hijacked', 'is_staff': True,
            'is_superuser': True, 'password': 'overwritten', 'line_id': 'my.line',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'profile-owner')
        self.assertFalse(self.user.is_staff)
        self.assertFalse(self.user.is_superuser)
        self.assertTrue(self.user.check_password(self.password))
        self.assertEqual(UserProfile.objects.get(user=self.other).line_id, 'other.line')

    def test_donor_contact_excludes_private_fields_and_inactive_users(self):
        response = self.client.get(f'/api/contacts/{self.other.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.data), {'username', 'whatsapp_number', 'line_id'})
        self.assertEqual(response.data['line_id'], 'other.line')
        self.assertIn('no-store', response['Cache-Control'])
        self.other.is_active = False
        self.other.save(update_fields=['is_active'])
        self.assertEqual(self.client.get(f'/api/contacts/{self.other.pk}/').status_code, 404)

    def test_delete_requires_password_and_confirmation_and_revokes_token(self):
        for data in ({'password': 'wrong', 'confirm': True},
                     {'password': self.password, 'confirm': False}, {}):
            self.assertEqual(self.client.delete('/api/profile/', data, format='json').status_code, 400)
        response = self.client.delete('/api/profile/',
            {'password': self.password, 'confirm': True}, format='json')
        self.assertEqual(response.status_code, 204)
        self.assertFalse(get_user_model().objects.filter(pk=self.user.pk).exists())
        self.assertFalse(UserProfile.objects.filter(user_id=self.user.pk).exists())
        self.assertFalse(Location.objects.filter(pk=self.location.pk).exists())
        self.assertFalse(Token.objects.filter(key=self.token.key).exists())
        self.assertTrue(get_user_model().objects.filter(pk=self.other.pk).exists())
        self.assertEqual(self.client.get('/api/profile/').status_code, 401)

    def test_session_writes_require_csrf_but_token_writes_work(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.patch('/api/profile/', {'line_id': 'blocked'}, format='json').status_code, 403)
        client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        self.assertEqual(client.patch('/api/profile/', {'line_id': 'allowed'}, format='json').status_code, 200)

    @override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                                         'LOCATION': 'userprofile-api-auth-test'}})
    def test_auth_endpoints_rate_limit_anonymous_requests(self):
        client = APIClient()
        for _ in range(20):
            self.assertEqual(client.post('/api/auth/login/', {}, format='json').status_code, 400)
        response = client.post('/api/auth/login/', {}, format='json')
        self.assertEqual(response.status_code, 429)
        self.assertIn('Retry-After', response)
