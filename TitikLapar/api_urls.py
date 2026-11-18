from django.urls import include, path
from rest_framework.routers import DefaultRouter

from SharedPost.api import SharedPostViewSet

router = DefaultRouter()
router.register('posts', SharedPostViewSet, basename='post')

app_name = 'api'
urlpatterns = [path('', include(router.urls))]
