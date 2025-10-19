from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from ecommerce.models import Store, Product, Review

User = get_user_model()


def ensure_group(name: str) -> Group:
    grp, _ = Group.objects.get_or_create(name=name)
    return grp


class ProductViewTests(TestCase):
    """
    Integration-style API tests for products, stores, and reviews.
    Uses URL names with the 'api' namespace as defined in api/urls.py.
    """

    def setUp(self):
        self.client = APIClient()

        # Users and groups
        self.vendor = User.objects.create_user("vendor1", password="x")
        self.other_vendor = User.objects.create_user("vendor2", password="x")
        self.buyer = User.objects.create_user("buyer1", password="x")

        vendors_group = ensure_group("Vendors")
        buyers_group = ensure_group("Buyers")

        vendors_group.user_set.add(self.vendor, self.other_vendor)
        buyers_group.user_set.add(self.buyer)

        # Ensure vendor and groups DON'T start with the price-change permission
        ct = ContentType.objects.get(app_label="ecommerce", model="product")
        self.price_perm = Permission.objects.get(
            content_type=ct, codename="can_change_product_price"
        )
        vendors_group.permissions.remove(self.price_perm)
        for g in self.vendor.groups.all():
            g.permissions.remove(self.price_perm)
        self.vendor.user_permissions.remove(self.price_perm)
        # Re-fetch to clear any cached perms on the user instance
        self.vendor = User.objects.get(pk=self.vendor.pk)

        # Stores
        self.store = Store.objects.create(
            name="Acme", description="", vendor=self.vendor
        )
        self.other_store = Store.objects.create(
            name="Other", description="", vendor=self.other_vendor
        )

        # Products
        self.prod = Product.objects.create(
            store=self.store, name="Widget", price=Decimal("10.00"), stock=2
        )
        self.other_prod = Product.objects.create(
            store=self.other_store, name="Gadget", price=Decimal("20.00"), stock=3
        )

        # URL helpers (namespace-aware)
        self.products_url = reverse("api:product-list")
        self.product_detail = lambda pk: reverse("api:product-detail", args=[pk])
        self.stores_url = reverse("api:store-list")
        self.vendor_store_list = lambda vid: reverse(
            "api:vendor-store-list", args=[vid]
        )
        self.store_product_list = lambda sid: reverse(
            "api:store-product-list", args=[sid]
        )
        self.product_reviews = lambda pid: reverse(
            "api:product-review-list", args=[pid]
        )

    # ---------- Products: reads open ----------

    def test_product_list_open(self):
        res = self.client.get(self.products_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(res.data), 2)

    def test_product_retrieve_open(self):
        res = self.client.get(self.product_detail(self.prod.pk))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["name"], "Widget")

    # ---------- Products: create restricted to Vendors + store ownership ----------

    def test_product_create_requires_vendor_and_store_ownership(self):
        payload = {
            "store": self.store.id,
            "name": "New P",
            "price": "12.34",
            "stock": 1,
        }

        # Anonymous
        res = self.client.post(self.products_url, payload, format="json")
        self.assertIn(
            res.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

        # Buyer (not vendor)
        self.client.force_authenticate(self.buyer)
        res = self.client.post(self.products_url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(None)

        # Vendor but not owner of 'store' -> serializer should block
        self.client.force_authenticate(self.other_vendor)
        res = self.client.post(self.products_url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.client.force_authenticate(None)

        # Correct vendor + owns store -> OK
        self.client.force_authenticate(self.vendor)
        res = self.client.post(self.products_url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["name"], "New P")
        self.client.force_authenticate(None)

    # ---------- Products: update/delete owner-only; price change needs permission ----------

    def test_product_update_only_owner_and_price_permission(self):
        self.client.force_authenticate(self.vendor)

        # Sanity check: vendor starts WITHOUT the price permission
        self.assertFalse(
            self.vendor.has_perm("ecommerce.can_change_product_price"),
            "Vendor unexpectedly already has the price-change permission!",
        )

        # Update name OK (owner)
        res = self.client.patch(
            self.product_detail(self.prod.pk),
            {"name": "Renamed"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["name"], "Renamed")

        # Update price without permission -> should be 403
        res = self.client.patch(
            self.product_detail(self.prod.pk),
            {"price": "99.99"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # Grant the custom permission and try again
        self.vendor.user_permissions.add(self.price_perm)

        # >>> IMPORTANT: refresh and re-authenticate so request.user sees new perms
        self.vendor = User.objects.get(pk=self.vendor.pk)  # refresh_from_db()
        self.client.force_authenticate(None)               # clear old auth
        self.client.force_authenticate(self.vendor)        # re-auth with updated user

        res = self.client.patch(
            self.product_detail(self.prod.pk),
            {"price": "99.99"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["price"], "99.99")

        self.client.force_authenticate(None)

    def test_product_update_denied_for_non_owner(self):
        self.client.force_authenticate(self.other_vendor)
        res = self.client.patch(
            self.product_detail(self.prod.pk), {"name": "Hack"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_product_delete_owner_only(self):
        # Non-owner denied
        self.client.force_authenticate(self.other_vendor)
        res = self.client.delete(self.product_detail(self.prod.pk))
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(None)

        # Owner allowed
        self.client.force_authenticate(self.vendor)
        res = self.client.delete(self.product_detail(self.prod.pk))
        self.assertIn(res.status_code, (status.HTTP_204_NO_CONTENT, status.HTTP_200_OK))

    # ---------- Stores ----------

    def test_store_create_sets_vendor_and_restricts_non_vendor(self):
        # Non-vendor rejected
        self.client.force_authenticate(self.buyer)
        res = self.client.post(
            self.stores_url, {"name": "S1", "description": ""}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # Vendor allowed and vendor auto-assigned
        self.client.force_authenticate(self.vendor)
        res = self.client.post(
            self.stores_url, {"name": "S2", "description": ""}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["vendor"], self.vendor.id)

    def test_vendor_store_list_filters_by_vendor(self):
        res = self.client.get(self.vendor_store_list(self.vendor.id))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(any(s["name"] == "Acme" for s in res.data))

        res = self.client.get(self.vendor_store_list(self.other_vendor.id))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(any(s["name"] == "Other" for s in res.data))

    def test_store_product_list_filters_by_store(self):
        res = self.client.get(self.store_product_list(self.store.id))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(any(p["name"] == "Widget" for p in res.data))
        self.assertFalse(any(p["name"] == "Gadget" for p in res.data))

    # ---------- Reviews ----------

    def test_reviews_list_public(self):
        res = self.client.get(self.product_reviews(self.prod.pk))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, [])

    def test_review_create_buyers_only_and_vendor_blocked(self):
        payload = {"rating": 5, "comment": "Great!"}

        # Vendor (owner) reviewing own product -> 403 (blocked)
        self.client.force_authenticate(self.vendor)
        res = self.client.post(self.product_reviews(self.prod.pk), payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(None)

        # Buyer OK
        self.client.force_authenticate(self.buyer)
        res = self.client.post(self.product_reviews(self.prod.pk), payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["rating"], 5)

        # Duplicate review by same buyer -> 400
        res = self.client.post(self.product_reviews(self.prod.pk), payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
