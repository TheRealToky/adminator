"""Auth + user management endpoints."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.core.permissions import IsAdmin

from .serializers import (
    AdminatorTokenObtainPairSerializer,
    PasswordChangeSerializer,
    RoleChoiceSerializer,
    UserCreateSerializer,
    UserSerializer,
)

User = get_user_model()


class LoginView(TokenObtainPairView):
    """POST email + password, receive access + refresh tokens + user payload."""

    serializer_class = AdminatorTokenObtainPairSerializer
    permission_classes: list = []  # public


class MeView(APIView):
    """Profile of the currently authenticated user."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserViewSet(viewsets.ModelViewSet):
    """Admins manage staff accounts."""

    queryset = User.objects.all().order_by("full_name")
    permission_classes = [IsAdmin]
    search_fields = ["full_name", "email"]
    filterset_fields = ["role", "is_active"]
    ordering_fields = ["full_name", "date_joined", "role"]

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        return UserSerializer

    @action(detail=True, methods=["post"], permission_classes=[IsAdmin])
    def deactivate(self, request, pk=None):
        user = self.get_object()
        user.is_active = False
        user.save(update_fields=["is_active"])
        return Response(UserSerializer(user).data)

    @action(detail=True, methods=["post"], permission_classes=[IsAdmin])
    def activate(self, request, pk=None):
        user = self.get_object()
        user.is_active = True
        user.save(update_fields=["is_active"])
        return Response(UserSerializer(user).data)


class RoleListView(APIView):
    """List available roles for UI dropdowns."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(RoleChoiceSerializer.list_all())
