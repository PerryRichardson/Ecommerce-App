# ecommerce/signals.py
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_migrate, post_save
from django.dispatch import receiver

from .models import Product


@receiver(post_migrate, dispatch_uid="ecommerce_seed_groups_perms_v1")
def create_groups_and_permissions(sender, **kwargs) -> None:
    """
    After the 'ecommerce' app migrates, ensure the 'Vendors' and 'Buyers' groups
    exist and that 'Vendors' has the custom can_change_product_price permission.
    """
    # Only run for our own app
    if getattr(sender, "label", None) != "ecommerce":
        return

    # Ensure groups exist
    vendors_group, _ = Group.objects.get_or_create(name="Vendors")
    Group.objects.get_or_create(name="Buyers")

    # Ensure the custom permission exists and attach it to Vendors
    ct: ContentType = ContentType.objects.get_for_model(Product)
    perm, _ = Permission.objects.get_or_create(
        content_type=ct,
        codename="can_change_product_price",
        defaults={"name": "Can change product price"},
    )
    vendors_group.permissions.add(perm)


@receiver(post_save, sender=Product, dispatch_uid="ecommerce_product_post_save_v1")
def product_saved(sender, instance, created, **kwargs) -> None:
    """Hook for side effects (e.g., logging or tweeting) when a product is created."""
    if created:
        # do something once (log, notify, etc.)
        pass
