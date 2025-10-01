# api/views.py
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.exceptions import PermissionDenied

from ecommerce.models import Product, Store
from .serializers import ProductSerializer, StoreSerializer
from .permissions import IsVendor, IsOwnerOrReadOnly


# -------- Products --------

class ProductListCreateAPIView(generics.ListCreateAPIView):
    """GET: list products (public) | POST: create (vendors only)."""
    queryset = Product.objects.select_related("store", "store__vendor")
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsVendor]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

class ProductDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """GET: read (public) | PATCH/PUT/DELETE: owner only (+ price perm for price changes)."""
    queryset = Product.objects.select_related("store", "store__vendor")
    serializer_class = ProductSerializer
    permission_classes = [IsOwnerOrReadOnly]

    def perform_update(self, serializer):
        if "price" in serializer.validated_data and not self.request.user.has_perm(
            "ecommerce.can_change_product_price"
        ):
            raise PermissionDenied("Missing 'ecommerce.can_change_product_price'.")
        serializer.save()

class StoreProductListAPIView(generics.ListAPIView):
    """GET: list products for a specific Store."""
    serializer_class = ProductSerializer

    def get_queryset(self):
        store_id = self.kwargs["store_id"]
        get_object_or_404(Store, pk=store_id)
        return Product.objects.filter(store_id=store_id).select_related("store", "store__vendor")

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
        ctx["request"] = self.request  # serializer will set vendor=request.user
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
        # FK is named 'store', so filtering on store_id is correct
        return Product.objects.filter(store_id=store_id).select_related("store", "vendor")
