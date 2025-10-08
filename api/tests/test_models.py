# api/tests/test_models.py

from api.serializers import ProductSerializer
from rest_framework.test import APIRequestFactory

def test_product_negative_price_validation(self):
    rf = APIRequestFactory()
    req = rf.post("/api/products/")
    req.user = self.vendor  # vendor owns the store; only price rule should fire

    payload = {"store": self.store.id, "name": "Bad", "price": "-0.01", "stock": 0}
    ser = ProductSerializer(data=payload, context={"request": req})
    self.assertFalse(ser.is_valid())
    self.assertIn("Price must be ≥ 0.", str(ser.errors))
