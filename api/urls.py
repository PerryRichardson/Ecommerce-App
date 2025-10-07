# api/urls.py
from django.urls import path
from .views import (
    ProductListCreateAPIView, ProductDetailAPIView,
    StoreListCreateAPIView, VendorStoreListAPIView, StoreProductListAPIView, 
    StoreReviewListCreateAPIView,
)

app_name = "api"

urlpatterns = [
    # Products
    path("products/", ProductListCreateAPIView.as_view(), name="product-list"),
    path("products/<int:pk>/", ProductDetailAPIView.as_view(), name="product-detail"),

    # Stores
    path("stores/", StoreListCreateAPIView.as_view(), name="store-list"),
    path("vendors/<int:vendor_id>/stores/", VendorStoreListAPIView.as_view(), name="vendor-store-list"),
    path("stores/<int:store_id>/products/", StoreProductListAPIView.as_view(), name="store-product-list"),

    # Reviews
     path("stores/<int:store_id>/reviews/", StoreReviewListCreateAPIView.as_view(), name="store-review-list"),   
]
