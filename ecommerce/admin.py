from django.contrib import admin
from .models import Store, Product, Order, OrderItem, Review


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "vendor", "product_count")
    list_select_related = ("vendor",)
    search_fields = ("name", "vendor__username")
    list_filter = ("vendor",)
    ordering = ("name",)

    @admin.display(description="Products")
    def product_count(self, obj: Store) -> int:
        return obj.products.count()


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "store", "price", "stock")
    list_select_related = ("store", "store__vendor")
    list_filter = ("store", "store__vendor")
    search_fields = ("name", "store__name")
    list_editable = ("price", "stock")
    ordering = ("name",)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    autocomplete_fields = ("product",)
    readonly_fields = ("line_total_calc",)
    fields = ("product", "qty", "price_snapshot", "line_total_calc")

    @admin.display(description="Line total")
    def line_total_calc(self, obj: OrderItem):
        if obj.pk:
            return obj.price_snapshot * obj.qty
        return "—"


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "created_at", "status", "total", "items_count")
    list_select_related = ("user",)
    list_filter = ("status", "created_at")
    search_fields = ("user__username", "id")
    date_hierarchy = "created_at"
    readonly_fields = ("created_at", "total")
    inlines = [OrderItemInline]
    ordering = ("-created_at",)

    @admin.display(description="Items")
    def items_count(self, obj: Order) -> int:
        return obj.items.count()


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("id", "product", "user", "rating", "verified", "created_at")
    list_select_related = ("product", "user")
    list_filter = ("verified", "rating", "product")
    search_fields = ("product__name", "user__username", "comment")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)


# Optional: personalize the admin
admin.site.site_header = "eCommerce Admin"
admin.site.site_title = "eCommerce Admin"
admin.site.index_title = "Administration"
