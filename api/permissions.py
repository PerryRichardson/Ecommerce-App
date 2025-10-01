from rest_framework.permissions import BasePermission, SAFE_METHODS

class IsVendor(BasePermission):
    """Allow writes only for users in Vendors group."""
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        u = request.user
        return u.is_authenticated and u.groups.filter(name="Vendors").exists()

class IsOwnerOrReadOnly(BasePermission):
    """Only the product owner's store vendor may modify; others can read."""
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        user_id = getattr(request.user, "id", None)
        # obj.store.vendor_id is the owner
        return (
            request.user.is_authenticated
            and getattr(getattr(obj, "store", None), "vendor_id", None) == user_id
        )
