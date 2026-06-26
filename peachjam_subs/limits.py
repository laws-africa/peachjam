"""Subscription-limited data locking.

When a user's active subscription has lower limits than their saved data, the
oldest over-limit items are locked instead of deleted. Locked items are ignored
by feature-limit checks and notification generation, but remain visible as
locked placeholders until the user upgrades or the retention window expires.

Upgrades unlock the newest locked items that fit within the new limits. Expired
locked items are purged by the subscription maintenance task.
"""

import logging
from dataclasses import dataclass

from django.db.models import Count, Min
from django.utils import timezone

from peachjam.customerio import get_customerio

log = logging.getLogger(__name__)

SUBSCRIPTION_LOCK_RETENTION_DAYS = 60


@dataclass(frozen=True)
class LimitedFeature:
    feature: str
    label: str
    model: object
    queryset_getter: object
    # Some models have destructive delete side effects. Folders delete saved
    # documents when they are the document's last folder, so expired locked
    # folders are only purged once empty.
    purge_empty_only: bool = False

    def queryset_for_user(self, user):
        return self.queryset_getter(user)


def limited_features():
    from peachjam.models import Folder, SavedDocument, UserFollowing
    from peachjam_search.models import SavedSearch

    return [
        LimitedFeature(
            "saved_document_limit",
            "saved_document",
            SavedDocument,
            lambda user: user.saved_documents.all(),
        ),
        LimitedFeature(
            "folder_limit",
            "folder",
            Folder,
            lambda user: user.folders.all(),
            purge_empty_only=True,
        ),
        LimitedFeature(
            "search_alert_limit",
            "search_alert",
            SavedSearch,
            lambda user: user.saved_searches.all(),
        ),
        LimitedFeature(
            "following_limit",
            "following",
            UserFollowing,
            lambda user: user.following.filter(
                saved_search__isnull=True,
                saved_document__isnull=True,
            ),
        ),
    ]


def lock_objects(queryset, now):
    objects = list(queryset)
    pks = [obj.pk for obj in objects]
    if not pks:
        return 0

    expires_at = now + timezone.timedelta(days=SUBSCRIPTION_LOCK_RETENTION_DAYS)
    count = queryset.model.objects.filter(pk__in=pks).update(
        subscription_locked_at=now,
        subscription_lock_expires_at=expires_at,
    )
    for obj in objects:
        log.info(
            "Subscription locked %s pk=%s object=%s until %s",
            obj._meta.label,
            obj.pk,
            obj,
            expires_at,
        )
    return count


def unlock_objects(queryset):
    objects = list(queryset)
    pks = [obj.pk for obj in objects]
    if not pks:
        return 0

    count = queryset.model.objects.filter(pk__in=pks).update(
        subscription_locked_at=None,
        subscription_lock_expires_at=None,
    )
    for obj in objects:
        log.info(
            "Subscription unlocked %s pk=%s object=%s",
            obj._meta.label,
            obj.pk,
            obj,
        )
    return count


def track_limited_data_locked(user, subscription, feature, locked_count, active_count):
    cio = get_customerio()
    if not hasattr(cio, "track_subscription_limited_data_locked"):
        return

    cio.track_subscription_limited_data_locked(
        user=user,
        subscription=subscription,
        feature=feature.label,
        locked_count=locked_count,
        active_count=active_count,
        limit=getattr(subscription.product_offering.product, feature.feature),
        expires_at=timezone.now()
        + timezone.timedelta(days=SUBSCRIPTION_LOCK_RETENTION_DAYS),
    )


def get_subscription_locked_data_summary(user):
    """Return a compact summary of subscription-locked data for user-facing warnings."""
    total_count = 0
    expires_at = None
    by_feature = {}

    for feature in limited_features():
        summary = (
            feature.queryset_for_user(user)
            .filter(subscription_locked_at__isnull=False)
            .aggregate(
                count=Count("pk"),
                earliest_expiry=Min("subscription_lock_expires_at"),
            )
        )
        feature_count = summary["count"]
        total_count += feature_count
        feature_expires_at = summary["earliest_expiry"]
        if feature_expires_at and (
            expires_at is None or feature_expires_at < expires_at
        ):
            expires_at = feature_expires_at
        if feature_count:
            by_feature[feature.label] = {
                "count": feature_count,
                "expires_at": feature_expires_at,
            }

    if not total_count:
        return None

    saved_documents = combine_locked_data_summaries(
        by_feature.get("saved_document"), by_feature.get("folder")
    )
    return {
        "count": total_count,
        "expires_at": expires_at,
        "by_category": {
            "saved_documents": saved_documents,
            "following": by_feature.get("following"),
            "search_alerts": by_feature.get("search_alert"),
        },
    }


def combine_locked_data_summaries(*summaries):
    count = 0
    expires_at = None

    for summary in summaries:
        if not summary:
            continue
        count += summary["count"]
        if summary["expires_at"] and (
            expires_at is None or summary["expires_at"] < expires_at
        ):
            expires_at = summary["expires_at"]

    if not count:
        return None
    return {
        "count": count,
        "expires_at": expires_at,
    }


def reconcile_user_subscription_limits(user, subscription):
    """Apply the active subscription's feature limits to the user's saved data.

    Only unlocked items count against limits. If the user is over a limit, the
    oldest unlocked items are locked until the retention deadline. If the user
    has spare capacity, the newest locked items are unlocked until the limit is
    filled or no locked items remain.
    """
    now = timezone.now()

    for feature in limited_features():
        limit = getattr(subscription.product_offering.product, feature.feature)
        base_qs = feature.queryset_for_user(user)
        unlocked_qs = base_qs.filter(subscription_locked_at__isnull=True)
        locked_qs = base_qs.filter(subscription_locked_at__isnull=False)
        active_count = unlocked_qs.count()

        if active_count > limit:
            lock_count = active_count - limit
            to_lock = unlocked_qs.order_by("created_at", "pk")[:lock_count]
            locked_count = lock_objects(to_lock, now)
            log.info(
                "Locked %s %s items for user %s after subscription limit reconciliation",
                locked_count,
                feature.label,
                user.pk,
            )
            track_limited_data_locked(
                user=user,
                subscription=subscription,
                feature=feature,
                locked_count=locked_count,
                active_count=active_count - locked_count,
            )
            continue

        unlock_count = min(limit - active_count, locked_qs.count())
        if unlock_count <= 0:
            continue

        to_unlock = locked_qs.order_by("-subscription_locked_at", "-created_at", "-pk")[
            :unlock_count
        ]
        unlocked_count = unlock_objects(to_unlock)
        log.info(
            "Unlocked %s %s items for user %s after subscription limit reconciliation",
            unlocked_count,
            feature.label,
            user.pk,
        )


def purge_expired_subscription_locked_data():
    now = timezone.now()
    total = 0

    for feature in limited_features():
        qs = feature.model.objects.filter(
            subscription_locked_at__isnull=False,
            subscription_lock_expires_at__lte=now,
        )
        if feature.purge_empty_only:
            qs = qs.filter(saved_documents__isnull=True)

        objects = list(qs)
        for obj in objects:
            log.info(
                "Purging expired subscription locked %s pk=%s object=%s",
                obj._meta.label,
                obj.pk,
                obj,
            )

        count, _ = qs.delete()
        total += count
        if count:
            log.info("Purged %s expired locked %s items", count, feature.label)

    return total
