from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Store(models.Model):
    vendor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="stores",
    )
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)

    def __str__(self) -> str:
        return f"{self.name} (by {self.vendor.username})"


class Product(models.Model):
    # NOTE: keep null=True/blank=True for now if you already have products
    # without a store; you can migrate to null=False later.
    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="products",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)

    class Meta:
        permissions = [
            ("can_change_product_price", "Can change product price"),
        ]

    def __str__(self) -> str:
        return self.name


class Order(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(max_length=20, default="paid")  # simple for module

    def __str__(self) -> str:
        return f"Order #{self.id} by {self.user.username}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    qty = models.PositiveIntegerField()
    price_snapshot = models.DecimalField(max_digits=10, decimal_places=2)

    def line_total(self):
        return self.price_snapshot * self.qty

    def __str__(self) -> str:
        return f"{self.product.name} x{self.qty} (Order #{self.order_id})"


class Review(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )  # 1..5
    comment = models.TextField(blank=True)
    verified = models.BooleanField(default=False)  # set True if user purchased
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "product"],
                name="unique_review_per_user_product",
            )
        ]

    def __str__(self) -> str:
        return f"Review {self.rating}/5 on {self.product_id} by {self.user_id}"

