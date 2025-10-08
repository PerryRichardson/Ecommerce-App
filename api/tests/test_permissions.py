# api/tests/test_permissions.py
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from api.permissions import IsVendor, IsBuyer, IsOwnerOrReadOnly
from ecommerce.models import Store, Product

User = get_user_model()


def ensure_group(name: str) -> Group:
    grp, _ = Group.objects.get_or_create(name=name)
    return grp


class PermissionTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

        # Users
        self.vendor = User.objects.create_user("vendor1", password="x")
        self.other_vendor = User.objects.create_user("vendor2", password="x")
        self.buyer = User.objects.create_user("buyer1", password="x")
        self.staff = User.objects.create_user("staff1", password="x", is_staff=True)
        self.anon = SimpleNamespace(is_authenticated=False)

        # Groups
        ensure_group("Vendors").user_set.add(self.vendor, self.other_vendor)
        ensure_group("Buyers").user_set.add(self.buyer)

        # Data
        self.vendor_store = Store.objects.create(name="Acme", description="", vendor=self.vendor)
        self.other_store = Store.objects.create(name="Other", description="", vendor=self.other_vendor)
        self.product = Product.objects.create(store=self.vendor_store, name="Widget", price="10.00", stock=2)

        # Dummy view object
        self.view = SimpleNamespace()

    # ---- IsVendor ----
    def test_isvendor_allows_safe_methods_to_anyone(self):
        req = self.factory.get("/api/products/")
        req.user = self.anon
        self.assertTrue(IsVendor().has_permission(req, self.view))

    def test_isvendor_denies_post_for_non_vendor(self):
        req = self.factory.post("/api/products/", {}); req.user = self.anon
        self.assertFalse(IsVendor().has_permission(req, self.view))
        req = self.factory.post("/api/products/", {}); req.user = self.buyer
        self.assertFalse(IsVendor().has_permission(req, self.view))

    def test_isvendor_allows_post_for_vendor(self):
        req = self.factory.post("/api/products/", {}); req.user = self.vendor
        self.assertTrue(IsVendor().has_permission(req, self.view))

    def test_isvendor_allows_post_for_staff(self):
        req = self.factory.post("/api/products/", {}); req.user = self.staff
        self.assertTrue(IsVendor().has_permission(req, self.view))

    # ---- IsBuyer ----
    def test_isbuyer_allows_safe_methods_to_anyone(self):
        req = self.factory.get(f"/api/products/{self.product.pk}/reviews/")
        req.user = self.anon
        self.assertTrue(IsBuyer().has_permission(req, self.view))

    def test_isbuyer_denies_post_for_non_buyer(self):
        req = self.factory.post(f"/api/products/{self.product.pk}/reviews/", {}); req.user = self.anon
        self.assertFalse(IsBuyer().has_permission(req, self.view))
        req = self.factory.post(f"/api/products/{self.product.pk}/reviews/", {}); req.user = self.vendor
        self.assertFalse(IsBuyer().has_permission(req, self.view))

    def test_isbuyer_allows_post_for_buyer(self):
        req = self.factory.post(f"/api/products/{self.product.pk}/reviews/", {}); req.user = self.buyer
        self.assertTrue(IsBuyer().has_permission(req, self.view))

    def test_isbuyer_allows_post_for_staff(self):
        req = self.factory.post(f"/api/products/{self.product.pk}/reviews/", {}); req.user = self.staff
        self.assertTrue(IsBuyer().has_permission(req, self.view))

    # ---- IsOwnerOrReadOnly ----
    def test_ownerorread_only_reads_open(self):
        req = self.factory.get(f"/api/products/{self.product.pk}/"); req.user = self.anon
        self.assertTrue(IsOwnerOrReadOnly().has_object_permission(req, self.view, self.product))

    def test_ownerorread_write_denied_for_anonymous(self):
        req = self.factory.patch(f"/api/products/{self.product.pk}/", {}); req.user = self.anon
        self.assertFalse(IsOwnerOrReadOnly().has_object_permission(req, self.view, self.product))

    def test_ownerorread_write_allowed_for_owner_vendor(self):
        req = self.factory.patch(f"/api/products/{self.product.pk}/", {"name": "New"}); req.user = self.vendor
        self.assertTrue(IsOwnerOrReadOnly().has_object_permission(req, self.view, self.product))

    def test_ownerorread_write_denied_for_non_owner_vendor(self):
        req = self.factory.patch(f"/api/products/{self.product.pk}/", {"name": "Hack"}); req.user = self.other_vendor
        self.assertFalse(IsOwnerOrReadOnly().has_object_permission(req, self.view, self.product))

    def test_ownerorread_write_allowed_for_staff(self):
        req = self.factory.delete(f"/api/products/{self.product.pk}/"); req.user = self.staff
        self.assertTrue(IsOwnerOrReadOnly().has_object_permission(req, self.view, self.product))

    def test_ownerorread_write_denied_if_obj_missing_store(self):
        class NoStoreObj: pass
        req = self.factory.patch("/api/nostore/1/", {}); req.user = self.vendor
        self.assertFalse(IsOwnerOrReadOnly().has_object_permission(req, self.view, NoStoreObj()))
