from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from ecommerce.models import Store, Product, Order, OrderItem, Review

User = get_user_model()


class ModelTests(TestCase):
    def setUp(self):
        self.vendor = User.objects.create_user(
            username="vendor1", password="x", email="v1@example.com"
        )
        self.buyer = User.objects.create_user(
            username="buyer1", password="x", email="b1@example.com"
        )
        self.store = Store.objects.create(
            name="Acme", description="Good stuff", vendor=self.vendor
        )
        self.prod = Product.objects.create(
            store=self.store,
            name="Widget",
            price=Decimal("9.99"),
            stock=5,
        )

    def test_store_str(self):
        # __str__ includes store name and vendor username
        self.assertIn("Acme", str(self.store))
        self.assertIn(self.vendor.username, str(self.store))

    def test_product_str(self):
        self.assertEqual(str(self.prod), "Widget")

    def test_product_negative_price_validation(self):
        p = Product(
            store=self.store,
            name="Bad",
            price=Decimal("-0.01"),
            stock=0,
        )
        # Model does not enforce nonnegative, but serializer does.
        # If you later add model-level validation, this will raise on full_clean()
        with self.assertRaises(ValidationError):
            p.full_clean()

    def test_unique_review_constraint(self):
        Review.objects.create(
            user=self.buyer, product=self.prod, rating=4, comment="Nice", verified=False
        )
        with self.assertRaises(IntegrityError):
            Review.objects.create(
                user=self.buyer, product=self.prod, rating=5, comment="Dup", verified=False
            )

    def test_order_item_line_total(self):
        order = Order.objects.create(user=self.buyer, total=Decimal("0.00"))
        item = OrderItem.objects.create(
            order=order,
            product=self.prod,
            qty=3,
            price_snapshot=Decimal("9.99"),
        )
        self.assertEqual(item.line_total(), Decimal("29.97"))
