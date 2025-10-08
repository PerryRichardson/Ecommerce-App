# api/permissions.py
from __future__ import annotations

from rest_framework.permissions import BasePermission, SAFE_METHODS


def _is_staff_or_superuser(user) -> bool:
    return bool(getattr(user, "is_staff", False) or getattr(user, "is_superuser", False))


class IsVendor(BasePermission):
    def has_permission(self, request, view) -> bool:
        if request.method in SAFE_METHODS:
            return True
        user = getattr(request, "user", None)
        if _is_staff_or_superuser(user):
            return True
        return bool(
            getattr(user, "is_authenticated", False)
            and user.groups.filter(name="Vendors").exists()
        )


class IsBuyer(BasePermission):
    def has_permission(self, request, view) -> bool:
        if request.method in SAFE_METHODS:
            return True
        user = getattr(request, "user", None)
        if _is_staff_or_superuser(user):
            return True
        return bool(
            getattr(user, "is_authenticated", False)
            and user.groups.filter(name="Buyers").exists()
        )


class IsOwnerOrReadOnly(BasePermission):
    def has_object_permission(self, request, view, obj) -> bool:
        if request.method in SAFE_METHODS:
            return True

        user = getattr(request, "user", None)
        if not getattr(user, "is_authenticated", False):
            return False
        if _is_staff_or_superuser(user):
            return True

        store = getattr(obj, "store", None)
        if store is None:
            return False

        vendor = getattr(store, "vendor", None)
        if vendor is not None:
            return getattr(vendor, "id", None) == getattr(user, "id", None)

        vendor_id = getattr(store, "vendor_id", None)
        return vendor_id == getattr(user, "id", None)
