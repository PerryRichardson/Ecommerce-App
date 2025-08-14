# ecommerce/tests.py
from decimal import Decimal

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core import mail
from django.test import TestCase, Client, override_settings
from django.urls import reverse

from .models import Product, Store, Order, OrderItem, Review


class BaseSetup(TestCase):
    """Shared fixtures & helpers for all tests."""

    @classmethod
    def setUpTestData(cls):
        # --- Groups & permission ---
        cls.group_vendors, _ = Group.objects.get_or_create(name="Vendors")
        cls.group_buyers, _ = Group.objects.get_or_create(name="Buyers")

        ct = ContentType.objects.get_for_model(Product)
        cls.perm_change_price, _ = Permission.objects.get_or_create(
            content_type=ct,
            codename="can_change_product_price",
            name="Can change product price",
        )
        cls.group_vendors.permissions.add(cls.perm_change_price)

        # --- Users ---
        cls.vendor_user = User.objects.create_user(
            username="alice_vendor", password="pass123", email="a@example.com"
        )
        cls.vendor_user.groups.add(cls.group_vendors)

        cls.buyer_user = User.objects.create_user(
            username="bob_buyer", password="pass123", email="b@example.com"
        )
        cls.buyer_user.groups.add(cls.group_buyers)

        # --- Store & Products ---
        cls.store = Store.objects.create(vendor=cls.vendor_user, name="Alice Shop")
        cls.product = Product.objects.create(
            store=cls.store, name="Widget", price=Decimal("10.00"), stock=10
        )
        cls.product2 = Product.objects.create(
            store=cls.store, name="Gadget", price=Decimal("25.50"), stock=5
        )

    # Helpers
    def login(self, username: str, password: str = "pass123") -> Client:
        client = Client()
        ok = client.login(username=username, password=password)
        self.assertTrue(ok, "Login helper failed.")
        return client

    def add_to_cart(self, client: Client, product_id: int, qty: int = 1):
        url = reverse("ecommerce:add_to_cart")
        return client.post(url, {"product_id": product_id, "qty": qty})


# ---------------- Auth & Registration ----------------

class AuthTests(BaseSetup):
    def test_register_assigns_groups(self):
        # Ensure groups exist (from BaseSetup)
        client = Client()
        url = reverse("ecommerce:register")

        # Register as vendor
        resp = client.post(
            url,
            {
                "username": "new_vendor",
                "password": "pass123",
                "email": "v@example.com",
                "account_type": "vendor",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        user = User.objects.get(username="new_vendor")
        self.assertTrue(user.groups.filter(name="Vendors").exists())

        # Register as buyer
        resp = client.post(
            url,
            {
                "username": "new_buyer",
                "password": "pass123",
                "email": "c@example.com",
                "account_type": "buyer",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        user = User.objects.get(username="new_buyer")
        self.assertTrue(user.groups.filter(name="Buyers").exists())

    def test_login_success_and_failure(self):
        client = Client()
        url = reverse("ecommerce:login")

        # Success
        resp = client.post(url, {"username": "bob_buyer", "password": "pass123"})
        self.assertEqual(resp.status_code, 302)

        # Failure
        resp = client.post(url, {"username": "bob_buyer", "password": "wrong"})
        self.assertEqual(resp.status_code, 302)  # redirected back with message


# ---------------- Permissions & Protected Views ----------------

class PermissionTests(BaseSetup):
    def test_vendor_dashboard_access(self):
        # Vendor: 200
        c_vendor = self.login("alice_vendor")
        resp = c_vendor.get(reverse("ecommerce:vendor_dashboard"))
        self.assertEqual(resp.status_code, 200)

        # Buyer: 403 (user_passes_test raises PermissionDenied)
        c_buyer = self.login("bob_buyer")
        resp = c_buyer.get(reverse("ecommerce:vendor_dashboard"))
        self.assertEqual(resp.status_code, 403)

        # Anonymous: redirect to login
        c_anon = Client()
        resp = c_anon.get(reverse("ecommerce:vendor_dashboard"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("ecommerce:login"), resp["Location"])

    def test_change_price_permission(self):
        url = reverse("ecommerce:change_price")

        # Vendor (has group permission) -> 200
        c_vendor = self.login("alice_vendor")
        resp = c_vendor.get(url)
        self.assertEqual(resp.status_code, 200)

        # Buyer (no permission) -> 403
        c_buyer = self.login("bob_buyer")
        resp = c_buyer.get(url)
        self.assertEqual(resp.status_code, 403)


# ---------------- Catalog Pages ----------------

class CatalogTests(BaseSetup):
    def test_store_list_page(self):
        resp = Client().get(reverse("ecommerce:catalog_store_list"))
        self.assertContains(resp, "Alice Shop", status_code=200)

    def test_product_list_page(self):
        url = reverse("ecommerce:catalog_product_list", args=[self.store.id])
        resp = Client().get(url)
        self.assertContains(resp, "Widget", status_code=200)

    def test_product_detail_page(self):
        url = reverse("ecommerce:catalog_product_detail", args=[self.product.id])
        resp = Client().get(url)
        self.assertContains(resp, "Widget", status_code=200)


# ---------------- Cart ----------------

class CartTests(BaseSetup):
    def test_add_update_remove_clear_cart(self):
        c = self.login("bob_buyer")

        # Add
        self.add_to_cart(c, self.product.id, 2)
        resp = c.get(reverse("ecommerce:view_cart"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("items", resp.context)
        self.assertEqual(len(resp.context["items"]), 1)
        self.assertEqual(resp.context["items"][0]["qty"], 2)

        # Update qty to 3
        url_update = reverse("ecommerce:update_cart_qty", args=[self.product.id])
        c.post(url_update, {"qty": 3})
        resp = c.get(reverse("ecommerce:view_cart"))
        self.assertEqual(resp.context["items"][0]["qty"], 3)

        # Remove
        url_remove = reverse("ecommerce:remove_from_cart", args=[self.product.id])
        c.post(url_remove)
        resp = c.get(reverse("ecommerce:view_cart"))
        self.assertEqual(resp.context["items"], [])

        # Clear cart (no error if already empty)
        url_clear = reverse("ecommerce:clear_cart")
        c.post(url_clear)
        resp = c.get(reverse("ecommerce:view_cart"))
        self.assertEqual(resp.context["items"], [])


# ---------------- Checkout / Orders ----------------

class CheckoutTests(BaseSetup):
    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_checkout_and_place_order(self):
        c = self.login("bob_buyer")

        # Add two products
        self.add_to_cart(c, self.product.id, 2)   # 2 * 10.00 = 20.00
        self.add_to_cart(c, self.product2.id, 1)  # 1 * 25.50 = 25.50

        # Checkout page shows totals
        resp = c.get(reverse("ecommerce:checkout"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("total", resp.context)
        self.assertEqual(resp.context["total"], Decimal("45.50"))

        # Place order
        resp = c.post(reverse("ecommerce:place_order"), follow=True)
        self.assertEqual(resp.status_code, 200)

        # Order created
        self.assertEqual(Order.objects.count(), 1)
        order = Order.objects.first()
        self.assertEqual(order.total, Decimal("45.50"))
        self.assertEqual(order.items.count(), 2)

        # Stock decremented
        self.product.refresh_from_db()
        self.product2.refresh_from_db()
        self.assertEqual(self.product.stock, 8)
        self.assertEqual(self.product2.stock, 4)

        # Cart cleared
        resp = c.get(reverse("ecommerce:view_cart"))
        self.assertEqual(resp.context["items"], [])

        # Email sent
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(f"Order #{order.id}", mail.outbox[0].subject)


# ---------------- Reviews ----------------

class ReviewTests(BaseSetup):
    def test_add_review_marks_verified_if_purchased(self):
        # Create a past order for the buyer with the product
        order = Order.objects.create(user=self.buyer_user, total=Decimal("10.00"))
        OrderItem.objects.create(order=order, product=self.product, qty=1, price_snapshot=Decimal("10.00"))

        c = self.login("bob_buyer")
        url = reverse("ecommerce:add_review", args=[self.product.id])
        resp = c.post(url, {"rating": 5, "comment": "Great!"})
        self.assertEqual(resp.status_code, 302)

        r = Review.objects.get(user=self.buyer_user, product=self.product)
        self.assertTrue(r.verified)
        self.assertEqual(r.rating, 5)
        self.assertEqual(r.comment, "Great!")

    def test_duplicate_review_blocked(self):
        # First review
        Review.objects.create(user=self.buyer_user, product=self.product, rating=4, comment="", verified=False)

        c = self.login("bob_buyer")
        url = reverse("ecommerce:add_review", args=[self.product.id])
        resp = c.post(url, {"rating": 5, "comment": "Another"})
        self.assertEqual(resp.status_code, 302)

        # Still only one review for that user+product
        self.assertEqual(Review.objects.filter(user=self.buyer_user, product=self.product).count(), 1)
