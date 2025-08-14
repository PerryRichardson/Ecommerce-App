from django.apps import AppConfig

class EcommerceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ecommerce'

    def ready(self):
        # Ensure signals are loaded
        from . import signals  # noqa: F401
