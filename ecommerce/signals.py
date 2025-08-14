from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_migrate
from django.dispatch import receiver

from .models import Product


@receiver(post_migrate)
def create_groups_and_permissions(sender, **kwargs) -> None:
    """
    After migrations for our app, ensure groups exist and Vendors has the
    custom 'can_change_product_price' permission.
    """
    # Only run when our own app finishes migrating
    if sender.label != 'ecommerce':
        return

    # Create (or get) the groups
    vendors_group, _ = Group.objects.get_or_create(name='Vendors')
    buyers_group, _ = Group.objects.get_or_create(name='Buyers')

    # Fetch our custom permission defined on Product.Meta.permissions
    content_type: ContentType = ContentType.objects.get_for_model(Product)
    try:
        can_change_price = Permission.objects.get(
            content_type=content_type,
            codename='can_change_product_price',
        )
        # Give Vendors this permission
        vendors_group.permissions.add(can_change_price)
    except Permission.DoesNotExist:
        # On a brand-new DB, this permission is created during the same migrate run.
        # If it isn't available yet on first run, the next migrate will pick it up.
        pass
