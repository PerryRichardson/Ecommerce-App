# Django eCommerce App

A small, educational eCommerce project built with Django. It demonstrates a complete flow: user auth with roles, vendor product management, public catalog, a session-based cart, checkout that creates orders, and product reviews.

This project was developed as part of a learning track to practice Django models, views, templates, permissions, and unit testing.
---

# Features:

### Core App (ecommerce/)
- Authentication: Register, Login, Logout
- User roles via Django Groups: Buyers and Vendors
- Custom permission: ecommerce.can_change_product_price

### Vendor area (/vendor/*)
- Vendor dashboard
- Create / edit / delete Stores
- Create/ edit / detete Products per store
- Session-based Cart: add, update qty, remove, clear
- Checkout: creates Order + OrderItems and reduces stock
- Email invoice (console backend in dev)

### Catalog and Cart (Public)
- Browse Stores and Products
- Product detail page (with "Add to cart" button)

### Reviews
- Leave 1–5 star reviews on products
- Reviews marked verified if the user purchased the product

---

##Technologies Used

- Python 3.13
- Django 5.x
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
