from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from Location.models import Location
from .forms import RegistrationForm
from .models import UserProfile


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField(max_length=254)
    password1 = serializers.CharField(write_only=True, trim_whitespace=False)
    password2 = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        self.form = RegistrationForm(attrs)
        if not self.form.is_valid():
            raise serializers.ValidationError(dict(self.form.errors))
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        user = self.form.save()
        UserProfile.objects.create(user=user)
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class ProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', max_length=254)

    class Meta:
        model = UserProfile
        fields = ('username', 'email', 'whatsapp_number', 'line_id', 'default_location')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            self.fields['default_location'].queryset = Location.objects.filter(owner=request.user)

    @transaction.atomic
    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', {})
        location = validated_data.get('default_location')
        if location:
            from django.shortcuts import get_object_or_404
            get_object_or_404(Location.objects.select_for_update(), pk=location.pk, owner=instance.user)
        if 'email' in user_data:
            get_user_model().objects.filter(pk=instance.user_id).update(email=user_data['email'])
            instance.user.email = user_data['email']
        return super().update(instance, validated_data)


class DeleteAccountSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    confirm = serializers.BooleanField()

    def validate(self, attrs):
        if not attrs['confirm']:
            raise serializers.ValidationError({'confirm': 'Konfirmasi penghapusan diperlukan.'})
        if not self.context['request'].user.check_password(attrs['password']):
            raise serializers.ValidationError({'password': 'Kata sandi tidak sesuai.'})
        return attrs
