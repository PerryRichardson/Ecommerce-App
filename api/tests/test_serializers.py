from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APIRequestFactory
from rest_framework import serializers

from ecommerce.models import Store, Product
from api.serializers import ProductSerializer, StoreSerializer, ReviewSerializer

User = get_user_model()


def ensure_group(name: str) -> Group:
    grp, _ = Group.objects.get_or_create(name=name)
    return grp


class SerializerTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.vendor = User.objects.create_user("vendor1", password="x")
        self.other_vendor = User.objects.create_user("vendor2", password="x")
        self.buyer = User.objects.create_user("buyer1", password="x")

        ensure_group("Vendors").user_set.add(self.vendor, self.other_vendor)
        ensure_group("Buyers").user_set.add(self.buyer)

        self.store = Store.objects.create(name="Acme", description="", vendor=self.vendor)
        self.other_store = Store.objects.create(name="Other", description="", vendor=self.other_vendor)

        self.product = Product.objects.create(
            store=self.store,
            name="Widget",
            price=Decimal("12.50"),
            stock=3,
        )

    def test_product_serializer_read_fields(self):
        request = self.factory.get("/api/products/")
        ser = ProductSerializer(instance=self.product, context={"request": request})
        data = ser.data
        self.assertEqual(data["name"], "Widget")
        self.assertEqual(data["store"], self.store.id)
        self.assertEqual(data["store_name"], "Acme")
        self.assertEqual(data["vendor_username"], self.vendor.username)

    def test_product_create_requires_vendor_group_and_store_ownership(self):
        # Authenticated but not vendor → rejected
        request = self.factory.post("/api/products/")
        request.user = self.buyer
        payload = {
            "store": self.store.id,
            "name": "New P",
            "price": "10.00",
            "stock": 1,
        }
        ser = ProductSerializer(data=payload, context={"request": request})
        self.assertFalse(ser.is_valid())
        self.assertIn("Only vendor users", str(ser.errors))

        # Vendor but wrong store owner → rejected
        request.user = self.other_vendor
        ser = ProductSerializer(data=payload, context={"request": request})
        self.assertFalse(ser.is_valid())
        self.assertIn("do not own this store", str(ser.errors))

        # Correct vendor + owns store → allowed
        request.user = self.vendor
        ser = ProductSerializer(data=payload, context={"request": request})
        self.assertTrue(ser.is_valid(), ser.errors)
        obj = ser.save()
        self.assertEqual(obj.store_id, self.store.id)
        self.assertEqual(obj.name, "New P")

    def test_product_update_respects_store_in_instance(self):
        # Move product to other store should be blocked by serializer validate()
        request = self.factory.patch("/api/products/1/")
        request.user = self.other_vendor  # not owner of self.product.store
        ser = ProductSerializer(
            instance=self.product,
            data={"name": "Renamed", "store": self.other_store.id},
            partial=True,
            context={"request": request},
        )
        self.assertFalse(ser.is_valid())
        self.assertIn("Changing the store of an existing product is not allowed", str(ser.errors))

    def test_store_create_assigns_vendor_from_request(self):
        request = self.factory.post("/api/stores/")
        request.user = self.vendor  # in Vendors
        payload = {"name": "New Store", "description": "Desc"}
        ser = StoreSerializer(data=payload, context={"request": request})
        self.assertTrue(ser.is_valid(), ser.errors)
        obj = ser.save()
        self.assertEqual(obj.vendor, self.vendor)

    def test_store_create_rejects_non_vendor(self):
        request = self.factory.post("/api/stores/")
        request.user = self.buyer  # not in Vendors
        payload = {"name": "New Store", "description": "Desc"}
        ser = StoreSerializer(data=payload, context={"request": request})
        self.assertTrue(ser.is_valid(), ser.errors)
        with self.assertRaisesMessage(serializers.ValidationError, "Only vendor users"):
            ser.save()

    def test_review_serializer_rating_validation(self):
        request = self.factory.post("/api/products/1/reviews/")
        request.user = self.buyer
        ser = ReviewSerializer(data={"rating": 6, "comment": "nope"}, context={"request": request})
        self.assertFalse(ser.is_valid())
        self.assertIn("less than or equal to 5", str(ser.errors))
