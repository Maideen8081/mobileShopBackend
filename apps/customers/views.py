from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.generics import GenericAPIView, ListAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Address
from .serializers import (
    AddressSerializer, AddressCreateSerializer,
    RegisterSerializer, LoginSerializer, UserSerializer,
    ChangePasswordSerializer,
)

User = get_user_model()


class AddressCreateAPIView(GenericAPIView):
    serializer_class = AddressCreateSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        is_default = serializer.validated_data.get('is_default', False)
        if request.user.is_authenticated and is_default:
            Address.objects.filter(user=request.user, is_default=True).update(is_default=False)

        address = serializer.save(user=request.user if request.user.is_authenticated else None)

        response_serializer = AddressSerializer(address)
        return Response({
            'success': True,
            'message': 'Address created successfully.',
            'data': response_serializer.data,
        }, status=status.HTTP_201_CREATED)


class AddressListAPIView(ListAPIView):
    serializer_class = AddressSerializer

    def get_queryset(self):
        if self.request.user.is_authenticated:
            return Address.objects.filter(user=self.request.user)
        return Address.objects.none()

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'data': serializer.data,
        })


class AddressUpdateAPIView(GenericAPIView):
    serializer_class = AddressCreateSerializer

    def put(self, request, *args, **kwargs):
        address_id = kwargs.get('address_id')
        try:
            address = Address.objects.get(id=address_id)
        except Address.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Address not found.',
            }, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(address, data=request.data)
        serializer.is_valid(raise_exception=True)

        is_default = serializer.validated_data.get('is_default', False)
        if request.user.is_authenticated and is_default:
            Address.objects.filter(user=request.user, is_default=True).exclude(id=address_id).update(is_default=False)

        address = serializer.save()

        response_serializer = AddressSerializer(address)
        return Response({
            'success': True,
            'message': 'Address updated successfully.',
            'data': response_serializer.data,
        })


class AddressDeleteAPIView(GenericAPIView):
    def delete(self, request, *args, **kwargs):
        address_id = kwargs.get('address_id')
        try:
            address = Address.objects.get(id=address_id)
        except Address.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Address not found.',
            }, status=status.HTTP_404_NOT_FOUND)

        was_default = address.is_default
        address.delete()

        if was_default:
            first = Address.objects.filter(user=request.user, is_default=True).first() if request.user.is_authenticated else None
            if first:
                first.is_default = True
                first.save()

        return Response({
            'success': True,
            'message': 'Address deleted successfully.',
        })


class AddressSetDefaultAPIView(GenericAPIView):
    def put(self, request, *args, **kwargs):
        address_id = kwargs.get('address_id')
        try:
            address = Address.objects.get(id=address_id)
        except Address.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Address not found.',
            }, status=status.HTTP_404_NOT_FOUND)

        if request.user.is_authenticated:
            Address.objects.filter(user=request.user, is_default=True).update(is_default=False)
        address.is_default = True
        address.save()

        response_serializer = AddressSerializer(address)
        return Response({
            'success': True,
            'message': 'Default address updated successfully.',
            'data': response_serializer.data,
        })


class RegisterAPIView(GenericAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)
        user_serializer = UserSerializer(user)

        return Response({
            'success': True,
            'message': 'Registration successful.',
            'data': {
                'user': user_serializer.data,
                'tokens': {
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                },
            },
        }, status=status.HTTP_201_CREATED)


class LoginAPIView(GenericAPIView):
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        refresh = RefreshToken.for_user(user)
        user_serializer = UserSerializer(user)

        return Response({
            'success': True,
            'message': 'Login successful.',
            'data': {
                'user': user_serializer.data,
                'tokens': {
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                },
            },
        })


class UserProfileAPIView(RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            'success': True,
            'data': serializer.data,
        })

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({
            'success': True,
            'message': 'Profile updated successfully.',
            'data': serializer.data,
        })


class ChangePasswordAPIView(GenericAPIView):
    serializer_class = ChangePasswordSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save()

        return Response({
            'success': True,
            'message': 'Password changed successfully.',
        })
