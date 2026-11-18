from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from TitikLapar.api_common import PrivateAPIResponseMixin
from .models import Notification
from .serializers import NotificationSerializer
from .views import generate_food_reminders


class NotificationViewSet(PrivateAPIResponseMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user).select_related('food_item')

    def list(self, request, *args, **kwargs):
        generate_food_reminders(recipient=request.user)
        return super().list(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save(update_fields=['is_read'])
        return Response(self.get_serializer(notification).data)

    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        return Response({'unread_count': self.get_queryset().filter(is_read=False).count()})

    @action(detail=False, methods=['post'])
    def refresh(self, request):
        # Generate only this account's reminders; delivery remains the scheduled job's responsibility.
        return Response(generate_food_reminders(recipient=request.user))
