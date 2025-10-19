# api/serializers.py
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict

from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from ecommerce.models import Product, Store, Review


class ProductSerializer(serializers.ModelSerializer):
    """
    Serializer for Product.
    - Validates non-negative price/stock.
    - Only Vendors can write; must own the store.
    - Forbids changing store on update.
    - Price update requires 'ecommerce.can_change_product_price'.
    """

    store_name = serializers.ReadOnlyField(source="store.name")
    vendor_username = serializers.ReadOnlyField(source="store.vendor.username")

    class Meta:
        model = Product
        fields = "__all__"

    # ---- field-level ----
    def validate_price(self, value: Decimal) -> Decimal:
        if value is None:
            raise serializers.ValidationError("Price is required.")
        if value < 0:
            raise serializers.ValidationError("Price must be ≥ 0.")
        return value

    def validate_stock(self, value: int) -> int:
        if value is None:
            raise serializers.ValidationError("Stock is required.")
        if value < 0:
            raise serializers.ValidationError("Stock must be ≥ 0.")
        return value

    # ---- object-level ----
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        request = self.context.get("request")
        if request and request.method in ("POST", "PUT", "PATCH"):
            user = request.user
            if not user or not user.is_authenticated:
                raise serializers.ValidationError("Authentication required.")

            if not user.groups.filter(name="Vendors").exists():
                raise serializers.ValidationError("Only vendor users can modify products.")

            store: Store | None = attrs.get("store") or getattr(self.instance, "store", None)
            if store is None:
                raise serializers.ValidationError({"store": "This field is required."})

            if store.vendor_id != user.id:
                raise serializers.ValidationError("You do not own this store.")

            if self.instance is not None and "store" in attrs:
                incoming_store: Store = attrs["store"]
                if incoming_store.pk != self.instance.store_id:
                    raise serializers.ValidationError(
                        {"store": "Changing the store of an existing product is not allowed."}
                    )

            # Friendly extra guard (decisive check also in `update`)
            if self.instance is not None and "price" in attrs:
                if not user.has_perm("ecommerce.can_change_product_price"):
                    raise PermissionDenied("Missing 'ecommerce.can_change_product_price'.")

        return attrs

    # ---- decisive guard for updates ----
    def update(self, instance: Product, validated_data: Dict[str, Any]) -> Product:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if "price" in validated_data:
            if not user or not user.has_perm("ecommerce.can_change_product_price"):
                raise PermissionDenied("Missing 'ecommerce.can_change_product_price'.")
        return super().update(instance, validated_data)


class StoreSerializer(serializers.ModelSerializer):
    vendor_username = serializers.ReadOnlyField(source="vendor.username")

    class Meta:
        model = Store
        fields = "__all__"
        read_only_fields = ("vendor",)

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
