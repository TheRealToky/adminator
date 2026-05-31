"""Role-aware DRF permissions."""
from __future__ import annotations

from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsAdmin(BasePermission):
    """Restricts to staff with the ADMIN role."""

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.is_admin)


class IsManagerOrAdmin(BasePermission):
    """Manager or Admin only."""

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and (user.is_admin or user.is_manager))


class ReadOnlyOrManager(BasePermission):
    """All authenticated staff can read; only managers/admins can write."""

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return user.is_admin or user.is_manager
