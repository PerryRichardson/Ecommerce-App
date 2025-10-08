# api/serializers.py
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict

from rest_framework import serializers

from ecommerce.models import Product, Store, Review


class ProductSerializer(serializers.ModelSerializer):
    """
    Serializer for Product.

    Hardening:
    - Validates non-negative price/stock.
    - Enforces that only Vendors can create/update.
    - Enforces that the logged-in vendor owns the target store.
    """

    # Helpful read-only context fields for responses
    store_name = serializers.ReadOnlyField(source="store.name")
    vendor_username = serializers.ReadOnlyField(source="store.vendor.username")

    class Meta:
        model = Product
        fields = "__all__"  # keep all model fields (store, name, price, stock, ...)
        # NOTE: Product does NOT have a direct 'vendor' FK (vendor is on Store).

    # ---- Field-level validators -------------------------------------------------

    def validate_price(self, value: Decimal) -> Decimal:
        if value is None:
            raise serializers.ValidationError("Price is required.")
        if value < 0:
            raise serializers.ValidationError("Price must be ≥ 0.")
        return value

    def validate_stock(self, value: int) -> int:
        # Your model uses PositiveIntegerField, but this gives a clearer API error.
        if value is None:
            raise serializers.ValidationError("Stock is required.")
        if value < 0:
            raise serializers.ValidationError("Stock must be ≥ 0.")
        return value

    # ---- Object-level validator -------------------------------------------------

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enforce permissions and ownership on writes.
        - Auth required.
        - User must be in Vendors group.
        - User must own the store associated with the product.
        """
        request = self.context.get("request")
        if request and request.method in ("POST", "PUT", "PATCH"):
            user = request.user
            if not user or not user.is_authenticated:
                raise serializers.ValidationError("Authentication required.")

            if not user.groups.filter(name="Vendors").exists():
                raise serializers.ValidationError("Only vendor users can modify products.")

            # On create we expect 'store' in attrs; on update we fall back to instance.store
            store: Store | None = attrs.get("store") or getattr(self.instance, "store", None)
            if store is None:
                raise serializers.ValidationError({"store": "This field is required."})

            if store.vendor_id != user.id:
                raise serializers.ValidationError("You do not own this store.")

        return attrs


class StoreSerializer(serializers.ModelSerializer):
    """
    Serializer for Store.

    Hardening:
    - Assigns vendor from request.user on create.
    - Ensures the creator is authenticated and in Vendors group.
    """

    vendor_username = serializers.ReadOnlyField(source="vendor.username")

    class Meta:
        model = Store
        fields = "__all__"
        read_only_fields = ("vendor",)

    # Optional: friendly validation
    def validate_name(self, value: str) -> str:
        if not value or not value.strip():
            raise serializers.ValidationError("Name cannot be blank.")
        return value.strip()

    def create(self, validated_data: Dict[str, Any]) -> Store:
        request = self.context.get("request")
        user = getattr(request, "user", None)

        if user is None or not user.is_authenticated:
            raise serializers.ValidationError("Authentication required.")

        if not user.groups.filter(name="Vendors").exists():
            raise serializers.ValidationError("Only vendor users can create stores.")

        validated_data["vendor"] = user
        return super().create(validated_data)


class ReviewSerializer(serializers.ModelSerializer):
    """
    Serializer for product reviews.

    Notes:
    - product, user, verified, created_at are set server-side in the view.
    - Model validators already restrict rating to 1..5; we add a friendly message.
    """

    user_username = serializers.ReadOnlyField(source="user.username")
    product_name = serializers.ReadOnlyField(source="product.name")

    class Meta:
        model = Review
        fields = [
            "id",
            "product",
            "product_name",
            "user",
            "user_username",
            "rating",
            "comment",
            "verified",
            "created_at",
        ]
        read_only_fields = ("product", "user", "verified", "created_at")

    def validate_rating(self, value: int) -> int:
        if value is None:
            raise serializers.ValidationError("Rating is required.")
        if not (1 <= value <= 5):
            raise serializers.ValidationError("Rating must be an integer between 1 and 5.")
        return value
