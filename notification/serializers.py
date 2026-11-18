from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ('id', 'food_item', 'title', 'message', 'is_read', 'created_at',
                  'reminder_days', 'expiry_date', 'email_status', 'email_sent_at')
        read_only_fields = fields
