from django.urls import include, path
from rest_framework.routers import DefaultRouter

from SharedPost.api import SharedPostViewSet
from userprofile.api import (DonorContactView, LoginView, LogoutView,
                             ProfileView, RegisterView)
from notification.api import NotificationViewSet

router = DefaultRouter()
router.register('posts', SharedPostViewSet, basename='post')
router.register('notifications', NotificationViewSet, basename='notification')

app_name = 'api'
urlpatterns = [
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('contacts/<int:user_id>/', DonorContactView.as_view(), name='contact'),
    path('', include(router.urls)),
]
