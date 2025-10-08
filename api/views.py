# api/views.py
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from ecommerce.models import Product, Store, Review
from .serializers import ProductSerializer, StoreSerializer, ReviewSerializer
from .permissions import IsVendor, IsOwnerOrReadOnly, IsBuyer


# -------- Products --------

class ProductListCreateAPIView(generics.ListCreateAPIView):
    """GET: list products (public) | POST: create (vendors only)."""
    queryset = Product.objects.select_related("store", "store__vendor")
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsVendor]

    # Note: DRF already injects request into serializer context by default.
    # Keeping this override is harmless, but not required.
    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx


class ProductDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET: read (public)
    PATCH/PUT/DELETE: owner only
    + price changes require 'ecommerce.can_change_product_price'.
    """
    queryset = Product.objects.select_related("store", "store__vendor")
    serializer_class = ProductSerializer
    permission_classes = [IsOwnerOrReadOnly]

    def perform_update(self, serializer):
        # IMPORTANT: key off request.data to detect submitted fields on PATCH.
        if "price" in self.request.data and not self.request.user.has_perm(
            "ecommerce.can_change_product_price"
        ):
            raise PermissionDenied("Missing 'ecommerce.can_change_product_price'.")
        serializer.save()


# -------- Stores --------

class StoreListCreateAPIView(generics.ListCreateAPIView):
    """
    GET: List all stores (public).
    POST: Create a store (authenticated + must be in Vendors).
    """
    queryset = Store.objects.all()
    serializer_class = StoreSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsVendor]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        # Serializer will assign vendor = request.user in create()
        ctx["request"] = self.request
        return ctx


class VendorStoreListAPIView(generics.ListAPIView):
    """GET: List all stores for a specific vendor id."""
    serializer_class = StoreSerializer

    def get_queryset(self):
        vendor_id = self.kwargs["vendor_id"]
        return Store.objects.filter(vendor_id=vendor_id)


class StoreProductListAPIView(generics.ListAPIView):
    """GET: list products that belong to a specific Store."""
    serializer_class = ProductSerializer

    def get_queryset(self):
        store_id = self.kwargs["store_id"]
        # 404 if the store doesn't exist (clearer than returning an empty list)
        get_object_or_404(Store, pk=store_id)
        # FK is named 'store'; traverse to store.vendor for serializer perf
        return (
            Product.objects.filter(store_id=store_id)
            .select_related("store", "store__vendor")
        )


# -------- Product Reviews (model is product-based) --------

class ProductReviewListCreateAPIView(generics.ListCreateAPIView):
    """
    GET: List reviews for a product (public).
    POST: Create a review for a product (Buyers only).
    """
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsBuyer]

    def get_queryset(self):
        product_id = self.kwargs["product_id"]
        get_object_or_404(Product, pk=product_id)
        return Review.objects.filter(product_id=product_id).select_related(
            "user", "product", "product__store"
        )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    def perform_create(self, serializer):
        product_id = self.kwargs["product_id"]
        product = get_object_or_404(Product, pk=product_id)

        # Note: Vendors are already blocked by IsBuyer (403).
        # The check below is an extra guard if roles change later.
        owner_vendor_id = getattr(getattr(product, "store", None), "vendor_id", None)
        if self.request.user.id == owner_vendor_id:
            raise ValidationError("Vendors cannot review their own product.")

        # Enforce one review per user per product (mirrors DB constraint).
        if Review.objects.filter(product=product, user=self.request.user).exists():
            raise ValidationError("You have already reviewed this product.")

        serializer.save(user=self.request.user, product=product)
