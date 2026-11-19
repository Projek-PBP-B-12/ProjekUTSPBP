from django.db import transaction
from django.db.models import F
from django.db.models.deletion import ProtectedError, RestrictedError
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from TitikLapar.api_common import PrivateAPIResponseMixin

from SharedPost.models import SharedPost
from SharedPost.services import get_map_pins
from django.utils import timezone
from .models import Location
from .serializers import LocationSerializer
from .views import LOCATION_IN_USE, _set_default


class LocationInUse(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = LOCATION_IN_USE


class LocationViewSet(PrivateAPIResponseMixin, viewsets.ModelViewSet):
    serializer_class = LocationSerializer
    filter_backends = (filters.SearchFilter,)
    search_fields = ('area_name',)

    def get_queryset(self):
        locations = Location.objects.filter(owner=self.request.user)
        if self.request.method in ('PUT', 'PATCH', 'DELETE', 'POST'):
            locations = locations.select_for_update()
        return locations

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def update(self, request, *args, **kwargs):
        with transaction.atomic():
            location = self.get_object()
            if location.shared_posts.exists():
                raise LocationInUse()
            return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                return super().destroy(request, *args, **kwargs)
        except (ProtectedError, RestrictedError):
            raise LocationInUse()

    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        with transaction.atomic():
            location = self.get_object()
            _set_default(request.user, location)
        return Response({'default_location': location.pk})

    @action(detail=False, methods=['get'])
    def pins(self, request):
        posts = SharedPost.objects.filter(
            is_active=True, food_item__status='OFFERED',
            food_item__expiration_date__gte=timezone.localdate(),
            food_item__owner__is_active=True,
            location__owner_id=F('food_item__owner_id'),
        )
        origin = Location.objects.filter(default_for_profiles__user=request.user, owner=request.user).first()
        return Response(get_map_pins(posts, origin=origin))
