from rest_framework import serializers
from ecommerce.models import Product, Store

class ProductSerializer(serializers.ModelSerializer):
    # Helpful read-only context fields
    store_name = serializers.ReadOnlyField(source="store.name")
    vendor_username = serializers.ReadOnlyField(source="store.vendor.username")

    class Meta:
        model = Product
        fields = "__all__"   # keep all model fields
        # NOTE: no "vendor" in read_only, because Product doesn't have it

    def validate(self, attrs):
        """Enforce: only the store owner (a Vendor) can create/update products."""
        request = self.context.get("request")
        if request and request.method in ("POST", "PUT", "PATCH"):
            if not request.user.is_authenticated:
                raise serializers.ValidationError("Authentication required.")
            # Expect a store on create; on update, use existing instance.store
            store = attrs.get("store") or getattr(self.instance, "store", None)
            if store is None:
                raise serializers.ValidationError({"store": "This field is required."})
            # Must be a Vendor
            if not request.user.groups.filter(name="Vendors").exists():
                raise serializers.ValidationError("Only vendor users can modify products.")
            # Must own the store
            if store.vendor_id != request.user.id:
                raise serializers.ValidationError("You do not own this store.")
        return attrs

class StoreSerializer(serializers.ModelSerializer):
    vendor_username = serializers.ReadOnlyField(source="vendor.username")

    class Meta:
        model = Store
        fields = "__all__"
        read_only_fields = ("vendor",)

    def create(self, validated_data):
        request = self.context.get("request")
        if request is None or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication required.")
        validated_data["vendor"] = request.user
        return super().create(validated_data)
