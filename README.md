# Django eCommerce App

A small, educational eCommerce project built with Django. It demonstrates a complete flow: user auth with roles, vendor product management, public catalog, a session-based cart, checkout that creates orders, and product reviews. Now includes a REST API (DRF) and optional tweet announcements.

This project was developed as part of a learning track to practice Django models, views, templates, permissions, and unit testing.
---

# Features:

### Core App (ecommerce/)
- Authentication: Register, Login, Logout
- User roles via Django Groups: Buyers and Vendors
- Custom permission: ecommerce.can_change_product_price
- Vendor area (/vendor/*)
  - Vendor dashboard
  - Create / edit / delete Stores
  - Create / edit / delete Products per store
- Session-based Cart: add, update qty, remove, clear
- Checkout: creates Order + OrderItems and reduces stock
- Email invoice (console backend in dev)
- Catalog (Public):
  - Browse Stores and Products
  - Product detail page (with “Add to cart”)

### Reviews
- Leave 1–5 star reviews on products
- Reviews marked verified if the user purchased the product
- Vendors are blocked from reviewing their own products
- One review per user per product

---
### REST API (api/ via Django REST Framework)
Public reads, restricted writes with clear ownership/role rules.

## Products
- GET /api/products/ — list products (public)
- POST /api/products/ — create (Vendors only & must own target store)
- GET /api/products/<id>/ — retrieve (public)
- PATCH/PUT /api/products/<id>/ — update (store owner only; changing price also requires ecommerce.can_change_product_price)
- DELETE /api/products/<id>/ — delete (store owner only)

## Stores
- GET /api/stores/ — list stores (public)
- POST /api/stores/ — create (Vendors only; vendor auto-assigned from request.user)
- GET /api/vendors/<vendor_id>/stores/ — list stores for a vendor

## Store → Products
- GET /api/stores/<store_id>/products/ — list products in a store

## Reviews
- GET /api/products/<product_id>/reviews/ — list reviews (public)
- POST /api/products/<product_id>/reviews/ — create (Buyers only; one per user; vendor of the product is blocked)

---
### Optional Tweet(X) Integration
Fire-and-forget tweets for new products and new reviews (off by default).
- Toggle in ecommerce_project/settings.py (or env)
---
## Technologies Used

- Python 3.13
- Django 5.x
- Django REST Framework
- MySQL for local dev (tests default to SQLite)
- HTML & CSS (via Django templates)
---

## Once installed, view apps at:
- http://127.0.0.1:8000/ → Welcome/Home
- http://127.0.0.1:8000/login/ → Login
- http://127.0.0.1:8000/register/ → Register
- http://127.0.0.1:8000/stores/ → Store list (catalog)
- http://127.0.0.1:8000/cart/ → Cart
- http://127.0.0.1:8000/checkout/ → Checkout
- http://127.0.0.1:8000/vendor/ → Vendor dashboard
- http://127.0.0.1:8000/admin/ → Django admin
- http://127.0.0.1:8000/api/ → API root (DRF)
