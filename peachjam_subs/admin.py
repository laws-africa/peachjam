from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django_fsm import TransitionNotAllowed
from guardian.admin import GuardedModelAdmin

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
class ProductOfferingAdmin(GuardedModelAdmin):
    list_display = ("product", "pricing_plan")
    search_fields = ("product__name", "pricing_plan__name")
    list_filter = ("product", "pricing_plan")


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "product_offering", "status", "created_at")
    search_fields = ("user__username", "product_offering__product__name")
    list_filter = ("product_offering", "status", "created_at")
    fields = [
        "user",
        "status",
        "product_offering",
        "starts_on",
        "ends_on",
        "created_at",
        "active_at",
        "closed_at",
        "start_of_current_period",
        "end_of_current_period",
    ]
    readonly_fields = [
        "created_at",
        "active_at",
        "closed_at",
        "status",
        "start_of_current_period",
        "end_of_current_period",
    ]

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ["user"]
        return self.readonly_fields

    def activate_subscription(self, request, subscription_id):
        if request.method == "POST":
            subscription = Subscription.objects.get(pk=subscription_id)
            try:
                subscription.activate()
                messages.success(request, _("Subscription activated."))
            except TransitionNotAllowed:
                messages.warning(request, _("Subscription cannot be activated."))
        return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/admin/"))

    def close_subscription(self, request, subscription_id):
        if request.method == "POST":
            subscription = Subscription.objects.get(pk=subscription_id)
            try:
                subscription.close()
                # ensure the user has an active subscription
                Subscription.get_or_create_active_for_user(request.user)
                messages.success(request, _("Subscription cancelled."))
            except TransitionNotAllowed:
                messages.warning(request, _("Subscription cannot be cancelled."))
        return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/admin/"))

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:subscription_id>/activate/",
                self.admin_site.admin_view(self.activate_subscription),
                name="peachjam_subs_subscription_activate",
            ),
            path(
                "<int:subscription_id>/close/",
                self.admin_site.admin_view(self.close_subscription),
                name="peachjam_subs_subscription_close",
            ),
        ]
        return custom_urls + urls


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
        "subscription_link",
        "status",
        "starts_on",
        "ends_on",
        "created_at",
        "active_at",
        "closed_at",
    ]
    readonly_fields = fields
    can_delete = False

    def subscription_link(self, obj):
        if obj.pk:
            url = reverse("admin:peachjam_subs_subscription_change", args=[obj.pk])
            return format_html('<a href="{}">{}</a>', url, obj)
        return "-"

    subscription_link.short_description = _("View")

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ["user"]
        return self.readonly_fields


UserAdminCustom.inlines = list(UserAdminCustom.inlines) + [SubscriptionInline]
