from django.contrib.auth import authenticate, get_user_model, logout
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError, RestrictedError
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters
from rest_framework import generics
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from TitikLapar.api_common import PrivateAPIResponseMixin

from .models import UserProfile
from .serializers import (DeleteAccountSerializer, LoginSerializer,
                          ProfileSerializer, RegisterSerializer)


class AuthRateThrottle(AnonRateThrottle):
    rate = '20/minute'


@method_decorator(sensitive_post_parameters('password', 'password1', 'password2'), name='dispatch')
class RegisterView(PrivateAPIResponseMixin, APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_classes = (AuthRateThrottle,)

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = serializer.save()
        except IntegrityError:
            if not get_user_model().objects.filter(username=serializer.validated_data['username']).exists():
                raise
            raise ValidationError({'username': 'Nama pengguna sudah digunakan.'})
        return Response({'id': user.pk, 'username': user.username}, status=201)


@method_decorator(sensitive_post_parameters('password'), name='dispatch')
class LoginView(RegisterView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(request=request, **serializer.validated_data)
        if user is None:
            return Response({'detail': 'Nama pengguna atau kata sandi tidak sesuai.'}, status=401)
        token, _ = Token.objects.get_or_create(user=user)
        return Response({'token': token.key, 'user_id': user.pk, 'username': user.username})


class LogoutView(PrivateAPIResponseMixin, APIView):
    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        logout(request)
        return Response(status=204)


@method_decorator(sensitive_post_parameters('password'), name='dispatch')
class ProfileView(PrivateAPIResponseMixin, generics.RetrieveUpdateAPIView):
    serializer_class = ProfileSerializer

    def get_object(self):
        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        return profile

    def delete(self, request):
        try:
            with transaction.atomic():
                user = get_object_or_404(get_user_model().objects.select_for_update(), pk=request.user.pk)
                request.user = user
                serializer = DeleteAccountSerializer(data=request.data, context={'request': request})
                serializer.is_valid(raise_exception=True)
                user.delete()
        except (ProtectedError, RestrictedError):
            return Response({'detail': 'Akun masih memiliki data terkait yang harus diselesaikan.'}, status=409)
        logout(request)
        return Response(status=204)


class DonorContactView(PrivateAPIResponseMixin, APIView):
    def get(self, request, user_id):
        donor = get_object_or_404(get_user_model(), pk=user_id, is_active=True)
        profile = UserProfile.objects.filter(user=donor).first()
        return Response({'username': donor.username,
                         'whatsapp_number': profile.whatsapp_number if profile else '',
                         'line_id': profile.line_id if profile else ''})
