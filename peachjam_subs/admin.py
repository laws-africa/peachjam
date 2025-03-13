from django.contrib import admin

from .models import PricingPlan, Product, ProductOffering, Subscription


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name",)


@admin.register(PricingPlan)
class PricingPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "period")
    search_fields = ("name",)
    list_filter = ("period",)


@admin.register(ProductOffering)
class ProductOfferingAdmin(admin.ModelAdmin):
    list_display = ("product", "pricing_plan")
    search_fields = ("product__name", "pricing_plan__name")
    list_filter = ("product", "pricing_plan")


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "product_offering", "active", "created_at")
    search_fields = ("user__username", "product_offering__product__name")
    list_filter = ("active", "created_at")

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ["user", "product_offering"]
        return []
