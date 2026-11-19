from rest_framework import serializers
from .models import Location


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ('id', 'owner', 'area_name', 'latitude', 'longitude')
        read_only_fields = ('owner',)
