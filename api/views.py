# api/views.py
from __future__ import annotations

import logging

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from ecommerce.models import Product, Review, Store
from .permissions import IsBuyer, IsOwnerOrReadOnly, IsVendor
from .serializers import ProductSerializer, ReviewSerializer, StoreSerializer

# --- optional tweet helper import (safe/no-op if missing) ---
try:
    from functions.tweet import get_tweet_client  # your helper
except Exception:  # pragma: no cover (tests shouldn’t depend on Twitter)
    get_tweet_client = None

logger = logging.getLogger(__name__)

# ---------- helpers ----------

def _user_has_price_perm(user) -> bool:
    """
    True if the user (or any of their groups) has the custom
    'ecommerce.can_change_product_price' permission for Product.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    ct = ContentType.objects.get_for_model(Product)
    return (
        user.user_permissions.filter(
            content_type=ct, codename="can_change_product_price"
        ).exists()
        or user.groups.filter(
            permissions__content_type=ct,
            permissions__codename="can_change_product_price",
        ).exists()
    )

def _tweet_safely(text: str, media_path: str | None = None) -> None:
    """
    Fire-and-forget tweet. Completely optional—never raises.
    Controlled by settings flags; if helper/env isn’t present, silently no-ops.
    """
    if not getattr(settings, "TWEET_ENABLED", False) or not text:
        return
    if get_tweet_client is None:
        logger.debug("Tweet skipped: get_tweet_client unavailable.")
        return
    try:
        client = get_tweet_client()
        if not client:
            logger.debug("Tweet skipped: client is None.")
            return
        ok = client.make_tweet(text=text, media_path=media_path)
        if ok:
            logger.info("Tweet posted.")
        else:
            logger.warning("Tweet helper returned False (not posted).")
    except Exception as e:  # pragma: no cover
        logger.warning("Tweet failed (non-fatal): %s", e)

# ---------- Products ----------

class ProductListCreateAPIView(generics.ListCreateAPIView):
    """GET: list products (public) • POST: create (vendors only)."""
    queryset = Product.objects.select_related("store", "store__vendor")
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsVendor]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    def perform_create(self, serializer):
        """
        Create the product, then (optionally) tweet about it.
        Tweeting is disabled by default. Enable with:
            TWEET_ENABLED = True
            TWEET_NEW_PRODUCT = True
        (plus credentials via env for the tweet client).
        """
        product = serializer.save()
        if getattr(settings, "TWEET_NEW_PRODUCT", False):
            store_name = getattr(product.store, "name", "a store")
            text = f"New product: {product.name} at {store_name} — {product.price}"
            _tweet_safely(text)

class ProductDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET: public
    PATCH/PUT/DELETE: owner only (IsOwnerOrReadOnly)
    • Any write that includes/changes 'price' must have 'ecommerce.can_change_product_price'.
    """
    queryset = Product.objects.select_related("store", "store__vendor")
    serializer_class = ProductSerializer
    permission_classes = [IsOwnerOrReadOnly]

    # --- hard guard *before* serializer/save ---

    def patch(self, request, *args, **kwargs):
        # If a PATCH attempts to set price, require the custom permission
        if "price" in (request.data or {}):
            if not _user_has_price_perm(request.user):
                raise PermissionDenied("Missing 'ecommerce.can_change_product_price'.")
        return super().patch(request, *args, **kwargs)

    def put(self, request, *args, **kwargs):
        # If a PUT attempts to set price, require the custom permission
        if "price" in (request.data or {}):
            if not _user_has_price_perm(request.user):
                raise PermissionDenied("Missing 'ecommerce.can_change_product_price'.")
        return super().put(request, *args, **kwargs)

    # --- defense in depth (if normalization hides it until validated_data) ---

    def perform_update(self, serializer):
        if "price" in getattr(serializer, "validated_data", {}):
            if not _user_has_price_perm(self.request.user):
                raise PermissionDenied("Missing 'ecommerce.can_change_product_price'.")
        serializer.save()

# ---------- Stores ----------

class StoreListCreateAPIView(generics.ListCreateAPIView):
    """GET: public • POST: vendors only (vendor set from request.user)."""
    queryset = Store.objects.all()
    serializer_class = StoreSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsVendor]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

class VendorStoreListAPIView(generics.ListAPIView):
    """GET: list all stores for a specific vendor id."""
    serializer_class = StoreSerializer

    def get_queryset(self):
        return Store.objects.filter(vendor_id=self.kwargs["vendor_id"])

class StoreProductListAPIView(generics.ListAPIView):
    """GET: list products that belong to a specific store."""
    serializer_class = ProductSerializer

    def get_queryset(self):
        store_id = self.kwargs["store_id"]
        get_object_or_404(Store, pk=store_id)
        return Product.objects.filter(store_id=store_id).select_related(
            "store", "store__vendor"
        )

# ---------- Reviews ----------

class ProductReviewListCreateAPIView(generics.ListCreateAPIView):
    """GET: list reviews (public) • POST: buyers only."""
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
        """
        Create a review with the same business rules as before,
        then (optionally) tweet about it.
        Enable with:
            TWEET_ENABLED = True
            TWEET_NEW_REVIEW = True
        """
        product = get_object_or_404(Product, pk=self.kwargs["product_id"])

        # Prevent vendor from reviewing their own product (tests expect 403)
        if self.request.user.id == getattr(product.store, "vendor_id", None):
            raise PermissionDenied("Vendors cannot review their own product.")

        # Enforce one review per user per product
        if Review.objects.filter(product=product, user=self.request.user).exists():
            raise ValidationError("You have already reviewed this product.")

        review = serializer.save(user=self.request.user, product=product)

        if getattr(settings, "TWEET_NEW_REVIEW", False):
            text = (
                f"New review for {product.name}: {review.rating}/5 "
                f"by {self.request.user.username}"
            )
            _tweet_safely(text)
