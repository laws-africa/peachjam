from django.contrib import admin
from django.contrib.auth import get_user_model
from django.shortcuts import redirect

from peachjam.admin import UserAdminCustom

from .models import (
    Feature,
    PricingPlan,
    Product,
    ProductOffering,
    Subscription,
    SubscriptionSettings,
    subscription_settings,
)


@admin.register(Feature)
class FeatureAdmin(admin.ModelAdmin):
    list_display = ("name", "ordering")
    search_fields = ("name",)
    filter_horizontal = ("permissions",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "description", "tier")
    search_fields = ("name",)
    readonly_fields = ("group",)
    filter_horizontal = ("features",)


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
    list_display = ("user", "product_offering", "status", "created_at")
    search_fields = ("user__username", "product_offering__product__name")
    list_filter = ("product_offering", "status", "created_at")
    readonly_fields = ["created_at"]

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ["user"]
        return self.readonly_fields


@admin.register(SubscriptionSettings)
class SubscriptionSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def changelist_view(self, request, extra_context=None):
        # redirect to edit the singleton
        return redirect(
            "admin:peachjam_subs_subscriptionsettings_change",
            subscription_settings().pk,
        )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.default_product_offering:
            users_without_subscription = get_user_model().objects.filter(
                subscriptions__isnull=True
            )
            for user in users_without_subscription:
                Subscription.objects.create(
                    user=user, product_offering=obj.default_product_offering
                )


class SubscriptionInline(admin.StackedInline):
    model = Subscription
    extra = 0
    fields = [
        "product_offering",
        "status",
        "created_at",
        "active_at",
        "closed_at",
        "start_of_current_period",
        "end_of_current_period",
    ]
    readonly_fields = fields
    can_delete = False

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ["user"]
        return self.readonly_fields


UserAdminCustom.inlines = list(UserAdminCustom.inlines) + [SubscriptionInline]
