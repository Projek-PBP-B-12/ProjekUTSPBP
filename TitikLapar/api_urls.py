from django.urls import include, path
from rest_framework.routers import DefaultRouter

from SharedPost.api import SharedPostViewSet
from notification.api import NotificationViewSet

router = DefaultRouter()
router.register('posts', SharedPostViewSet, basename='post')
router.register('notifications', NotificationViewSet, basename='notification')

app_name = 'api'
urlpatterns = [path('', include(router.urls))]
