from django.utils import timezone
from django.utils.html import strip_tags
from urllib.parse import urlsplit
from rest_framework import serializers

from .models import FoodItem


class OptionalFoodDateField(serializers.DateField):
    """Tanggal kosong pada form web berarti hari ini, bukan NULL di database."""

    def run_validation(self, data=serializers.empty):
        if data is None or data == '':
            return timezone.localdate()
        return super().run_validation(data)


class FoodItemSerializer(serializers.ModelSerializer):
    purchase_date = OptionalFoodDateField(required=False)
    expiration_date = OptionalFoodDateField(required=False)
    days_until_expiration = serializers.IntegerField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = FoodItem
        fields = ('id', 'owner', 'name', 'category', 'purchase_date',
                  'expiration_date', 'status', 'image_url', 'created_at',
                  'updated_at', 'days_until_expiration', 'is_expired')
        read_only_fields = ('owner', 'status', 'created_at', 'updated_at')

    def validate_image_url(self, value):
        if value and urlsplit(value).scheme not in ('http', 'https'):
            raise serializers.ValidationError('Gunakan URL foto HTTP/HTTPS.')
        return value

    def validate_name(self, value):
        value = strip_tags(value).strip()
        if not value:
            raise serializers.ValidationError('Nama makanan wajib diisi.')
        return value

    def validate(self, attrs):
        today = timezone.localdate()
        for field in ('purchase_date', 'expiration_date'):
            if not self.instance:
                attrs.setdefault(field, today)
        purchase = attrs.get('purchase_date', getattr(self.instance, 'purchase_date', today))
        expiry = attrs.get('expiration_date', getattr(self.instance, 'expiration_date', today))
        if expiry < purchase:
            raise serializers.ValidationError({'expiration_date': 'Tanggal kedaluwarsa harus setelah atau sama dengan tanggal beli.'})
        return attrs


class FoodStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=('STORED', 'CONSUMED', 'OFFERED'))
