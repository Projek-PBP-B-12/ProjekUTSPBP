from rest_framework import serializers
from FoodItem.models import FoodItem
from Location.models import Location
from .forms import SharedPostForm
from .models import SharedPost


class SharedPostSerializer(serializers.ModelSerializer):
    food_name = serializers.CharField(source='food_item.name', read_only=True)
    expiration_date = serializers.DateField(source='food_item.expiration_date', read_only=True)
    owner = serializers.IntegerField(source='food_item.owner_id', read_only=True)
    area_name = serializers.CharField(source='location.area_name', read_only=True)

    class Meta:
        model = SharedPost
        fields = ('id', 'food_item', 'food_name', 'expiration_date', 'owner',
                  'location', 'area_name', 'description', 'is_active', 'created_at', 'updated_at')
        read_only_fields = ('is_active', 'created_at', 'updated_at')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            self.fields['food_item'].queryset = FoodItem.objects.filter(owner=request.user)
            self.fields['location'].queryset = Location.objects.filter(owner=request.user)

    def validate(self, attrs):
        if self.instance and 'food_item' in attrs and attrs['food_item'].pk != self.instance.food_item_id:
            raise serializers.ValidationError({'food_item': 'Makanan pada penawaran tidak dapat diganti.'})
        data = {
            key: getattr(attrs.get(key), 'pk', attrs.get(key))
            if key in attrs else getattr(self.instance, key + '_id' if key != 'description' else key, None)
            for key in ('food_item', 'location', 'description')
        }
        form = SharedPostForm(data, instance=self.instance, user=self.context['request'].user)
        if not form.is_valid():
            raise serializers.ValidationError(dict(form.errors))
        attrs['description'] = form.cleaned_data['description']
        return attrs
