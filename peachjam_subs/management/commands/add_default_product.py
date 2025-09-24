import logging

from django.conf import settings
from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand
from django.db import transaction

from peachjam_subs.models import (
    Feature,
    PricingPlan,
    Product,
    ProductOffering,
    subscription_settings,
)

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Backfill default product and its features"
    FEATURES = {
        "legislation": {
            "name": "National, provincial and municipal legislation",
            "permissions": [],
            "order": 1,
        },
        "judgments": {
            "name": "Court judgments",
            "permissions": [],
            "order": 2,
        },
        "gazettes": {
            "name": "Government gazettes",
            "permissions": [],
            "order": 3,
        },
        "annotations": {
            "name": "Private annotations on documents",
            "permissions": [
                "peachjam.add_annotation",
                "peachjam.change_annotation",
                "peachjam.delete_annotation",
                "peachjam.view_annotation",
            ],
            "order": 4,
        },
        "ai_suggestions": {
            "name": "AI-powered research suggestions",
            "permissions": [
                "peachjam_ml.view_documentembedding",
            ],
            "order": 5,
        },
        "search_alerts": {
            "name": "Search alerts",
            "permissions": [
                "peachjam_search.add_savedsearch",
                "peachjam_search.change_savedsearch",
                "peachjam_search.delete_savedsearch",
                "peachjam_search.view_savedsearch",
            ],
            "order": 6,
        },
        "follow_topics": {
            "name": "Follow courts and topics of interest",
            "permissions": [
                "peachjam.add_userfollowing",
                "peachjam.change_userfollowing",
                "peachjam.delete_userfollowing",
                "peachjam.view_userfollowing",
            ],
            "order": 7,
        },
        "provision_citations": {
            "name": "Provision citations",
            "permissions": [
                "peachjam.view_provisioncitation",
            ],
            "order": 8,
        },
        "case_summaries": {
            "name": "Case summaries",
            "permissions": [
                "peachjam.can_view_document_summary",
            ],
            "order": 9,
        },
        "case_histories": {
            "name": "Case histories",
            "permissions": [],
            "order": 10,
        },
        "historical_legislation": {
            "name": "Historical versions of legislation",
            "permissions": [],
            "order": 11,
        },
        "search_download": {
            "name": "Download search results",
            "permissions": [
                "peachjam.can_download_search",
            ],
            "order": 12,
        },
        "semantic_search": {
            "name": "AI-powered semantic search",
            "permissions": [
                "peachjam_ml.can_use_semantic_search",
            ],
            "order": 13,
        },
        "unconsitutional_provisions": {
            "name": "Unconstitutional provisions",
            "permissions": [
                "peachjam.view_unconstitutionalprovision",
            ],
            "order": 14,
        },
        "uncommenced_provisions": {
            "name": "Uncommenced provisions",
            "permissions": [
                "peachjam.view_uncommencedprovision",
            ],
            "order": 15,
        },
    }

    def handle(self, *args, **kwargs):
        with transaction.atomic():
            log.info("Starting backfill of default product and its features")
            sub_settings = subscription_settings()

            default_product_offering = sub_settings.default_product_offering
            if not default_product_offering:
                log.info(
                    "No default product offering set. Creating default product, pricing plan, and product offering."
                )
                app_name = settings.PEACHJAM.get("APP_NAME") or "LII"
                product, _ = Product.objects.get_or_create(
                    name=f"My {app_name}",
                    defaults={
                        "description": "Full access to all foundational legal information."
                    },
                )
                pricing_plan, _ = PricingPlan.objects.get_or_create(
                    name__iexact="Free",
                    defaults={"name": "Free", "price": 0, "period": "annually"},
                )
                product_offering, _ = ProductOffering.objects.get_or_create(
                    product=product,
                    pricing_plan=pricing_plan,
                )

                sub_settings.default_product_offering = product_offering
                sub_settings.save()

            product = sub_settings.default_product_offering.product
            log.info(f"Using product '{product.name}' (ID: {product.id})")

            for slug, data in self.FEATURES.items():
                log.info(f"Processing feature '{data['name']}'")
                feature, _ = Feature.objects.get_or_create(
                    name=data["name"],
                    defaults={
                        "ordering": data["order"],
                    },
                )

                # attach permissions if not already linked
                for perm_string in data["permissions"]:
                    log.info(
                        f"Attaching permission '{perm_string}' to feature '{data['name']}'"
                    )
                    app_label, codename = perm_string.split(".")
                    try:
                        log.info(
                            f"Looking up permission with app_label '{app_label}' and codename '{codename}'"
                        )
                        perm = Permission.objects.get(
                            content_type__app_label=app_label,
                            codename=codename,
                        )
                        log.info(
                            f"Found permission '{perm}'. Attaching to feature '{data['name']}'"
                        )
                        feature.permissions.add(perm)

                    except Permission.DoesNotExist:
                        log.warning(
                            f"Permission '{perm_string}' does not exist. Skipping."
                        )
                        continue

                # attach feature to product
                log.info(
                    f"Attaching feature '{data['name']}' to product '{product.name}'"
                )
                product.features.add(feature)
