from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import Throttled, ValidationError
from rest_framework.response import Response
from TitikLapar.api_common import PrivateAPIResponseMixin

from FoodItem.models import FoodItem
from Location.models import Location
from .decorators import _take_write_slot
from .models import SharedPost
from .serializers import SharedPostSerializer
from .views import _locked_post_and_food


class SharedPostViewSet(PrivateAPIResponseMixin, viewsets.ModelViewSet):
    serializer_class = SharedPostSerializer
    filter_backends = (filters.SearchFilter, filters.OrderingFilter)
    search_fields = ('food_item__name', 'location__area_name')
    ordering_fields = ('created_at', 'food_item__expiration_date')
    ordering = ('-created_at', '-pk')

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            wait = _take_write_slot(request.user.pk,
                getattr(settings, 'SHAREDPOST_WRITE_LIMIT', 20),
                getattr(settings, 'SHAREDPOST_WRITE_WINDOW_SECONDS', 60))
            if wait:
                raise Throttled(wait=wait)

    def get_queryset(self):
        posts = SharedPost.objects.select_related('food_item__owner', 'location')
        if self.request.method not in ('GET', 'HEAD', 'OPTIONS'):
            return posts.filter(food_item__owner=self.request.user)
        available = Q(is_active=True, food_item__status='OFFERED',
                      food_item__expiration_date__gte=timezone.localdate(), food_item__owner__is_active=True)
        if self.action == 'retrieve':
            return posts.filter(available | Q(food_item__owner=self.request.user))
        posts = posts.filter(available)
        if self.request.query_params.get('mine') == '1':
            posts = posts.filter(food_item__owner=self.request.user)
        category = self.request.query_params.get('category')
        return posts.filter(food_item__category=category) if category else posts

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        list(FoodItem.objects.select_for_update().filter(owner=request.user).order_by('pk'))
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        location = get_object_or_404(Location.objects.select_for_update(), pk=serializer.validated_data['location'].pk, owner=self.request.user)
        post = serializer.save(location=location)
        post.food_item.status = 'OFFERED'
        post.food_item.save(update_fields=['status', 'updated_at'])

    def _lock_owned(self):
        post, food = _locked_post_and_food(self.request.user, self.kwargs['pk'])
        post.food_item = food
        return post

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        post = self._lock_owned()
        if not post.is_active:
            raise ValidationError('Penawaran sudah tidak aktif.')
        return super().update(request, *args, **kwargs)

    def perform_update(self, serializer):
        location = get_object_or_404(Location.objects.select_for_update(), pk=serializer.validated_data.get('location', serializer.instance.location).pk, owner=self.request.user)
        serializer.save(location=location)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        post = self._lock_owned()
        if post.is_active and post.food_item.status == 'OFFERED':
            post.food_item.status = 'STORED'
            post.food_item.save(update_fields=['status', 'updated_at'])
        post.delete()
        return Response(status=204)

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def complete(self, request, pk=None):
        post = self._lock_owned()
        if not post.is_active:
            raise ValidationError('Penawaran sudah tidak aktif.')
        post.is_active = False
        post.save(update_fields=['is_active', 'updated_at'])
        post.food_item.status = 'CONSUMED'
        post.food_item.save(update_fields=['status', 'updated_at'])
        return Response(self.get_serializer(post).data)
