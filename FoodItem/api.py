from django.db import transaction
from django.utils import timezone
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from TitikLapar.api_common import PrivateAPIResponseMixin

from .models import FoodItem
from .serializers import FoodItemSerializer, FoodStatusSerializer
from .views import _change_status, _schedule_food_reminders


class FoodItemViewSet(PrivateAPIResponseMixin, viewsets.ModelViewSet):
    serializer_class = FoodItemSerializer
    filter_backends = (filters.SearchFilter, filters.OrderingFilter)
    search_fields = ('name',)
    ordering_fields = ('expiration_date', 'name', 'created_at')
    ordering = ('expiration_date', 'pk')

    def get_queryset(self):
        foods = FoodItem.objects.filter(owner=self.request.user)
        if self.request.method in ('PUT', 'PATCH', 'DELETE'):
            foods = foods.select_for_update()
        return foods

    def perform_create(self, serializer):
        with transaction.atomic():
            food = serializer.save(owner=self.request.user)
            _schedule_food_reminders(food)

    def update(self, request, *args, **kwargs):
        with transaction.atomic():
            return super().update(request, *args, **kwargs)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    def perform_update(self, serializer):
        was_expired = serializer.instance.is_expired
        food = serializer.save()
        if was_expired or food.is_expired:
            food.shared_posts.filter(is_active=True).update(is_active=False, updated_at=timezone.now())
            if food.status == 'OFFERED':
                food.status = 'STORED'
                food.save(update_fields=['status', 'updated_at'])
        _schedule_food_reminders(food)

    @action(detail=True, methods=['post'], url_path='status')
    def change_status(self, request, pk=None):
        food = self.get_object()
        serializer = FoodStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data, code = _change_status(request.user, food.pk, serializer.validated_data['status'])
        return Response(data, status=code)
