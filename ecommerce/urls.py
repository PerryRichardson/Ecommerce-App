# ecommerce/urls.py
from django.urls import path
from . import views

app_name = 'ecommerce'

urlpatterns = [
    # existing routes...
    path('register/', views.register_user, name='register'),
    path('login/', views.login_user, name='login'),
    path('welcome/', views.welcome, name='welcome'),
    path('logout/', views.logout_user, name='logout'),
    path('vendor-dashboard/', views.vendor_dashboard, name='vendor_dashboard'),
    path('change-price/', views.change_price, name='change_price'),

    # cart
    path('cart/', views.view_cart, name='view_cart'),
    path('cart/add/', views.add_to_cart, name='add_to_cart'),
    path('cart/remove/<int:product_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/update/<int:product_id>/', views.update_cart_qty, name='update_cart_qty'),
    path('cart/clear/', views.clear_cart, name='clear_cart'),

    # NEW: store CRUD (vendor-only)
    path('vendor/stores/', views.store_list, name='store_list'),
    path('vendor/stores/new/', views.store_create, name='store_create'),
    path('vendor/stores/<int:pk>/edit/', views.store_update, name='store_update'),
    path('vendor/stores/<int:pk>/delete/', views.store_delete, name='store_delete'),

    # NEW: product CRUD (vendor-only)
    path('vendor/products/', views.product_list, name='product_list'),
    path('vendor/products/new/', views.product_create, name='product_create'),
    path('vendor/products/<int:pk>/edit/', views.product_update, name='product_update'),
    path('vendor/products/<int:pk>/delete/', views.product_delete, name='product_delete'),

    # Catalog (buyer)
    path('stores/', views.catalog_store_list, name='catalog_store_list'),
    path('stores/<int:store_id>/', views.catalog_product_list, name='catalog_product_list'),
    path('products/<int:pk>/', views.catalog_product_detail, name='catalog_product_detail'),

    # Checkout
    path('checkout/', views.checkout, name='checkout'),
    path('checkout/place/', views.place_order, name='place_order'),
    path('checkout/success/<int:order_id>/', views.order_success, name='order_success'),

    # Review product
    path('products/<int:pk>/review/', views.add_review, name='add_review'),
]
