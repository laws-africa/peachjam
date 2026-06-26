from datetime import timedelta
from decimal import Decimal

from countries_plus.models import Country
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from peachjam.models import CoreDocument, Court, Folder, SavedDocument, UserFollowing
from peachjam_search.models import SavedSearch
from peachjam_subs.limits import (
    SUBSCRIPTION_LOCK_RETENTION_DAYS,
    purge_expired_subscription_locked_data,
    reconcile_user_subscription_limits,
)
from peachjam_subs.models import PricingPlan, Product, ProductOffering, Subscription


class SubscriptionLockedDataTest(TestCase):
    fixtures = [
        "tests/countries",
        "documents/sample_documents",
        "tests/users",
        "tests/products",
    ]

    def setUp(self):
        self.user = User.objects.first()
        Subscription.objects.filter(user=self.user).delete()
        self.user.following.all().delete()
        self.user.saved_searches.all().delete()
        self.user.saved_documents.all().delete()
        self.user.folders.all().delete()

        plan = PricingPlan.objects.create(
            name="Lock test monthly",
            price=Decimal("0.00"),
            period=PricingPlan.Period.MONTHLY,
        )
        self.low_product = Product.objects.create(
            name="Lock test low",
            tier=1,
            saved_document_limit=1,
            folder_limit=1,
            search_alert_limit=1,
            following_limit=1,
        )
        self.mid_product = Product.objects.create(
            name="Lock test mid",
            tier=2,
            saved_document_limit=2,
            folder_limit=2,
            search_alert_limit=2,
            following_limit=2,
        )
        self.low_offering = ProductOffering.objects.create(
            product=self.low_product,
            pricing_plan=plan,
        )
        self.mid_offering = ProductOffering.objects.create(
            product=self.mid_product,
            pricing_plan=plan,
        )

    def create_saved_documents(self, count):
        docs = []
        works = []
        for doc in CoreDocument.objects.order_by("pk"):
            if doc.work_id not in [work.pk for work in works]:
                works.append(doc.work)
            if len(works) == count:
                break

        for index, work in enumerate(works):
            saved_doc = SavedDocument.objects.create(user=self.user, work=work)
            SavedDocument.objects.filter(pk=saved_doc.pk).update(
                created_at=timezone.now() - timedelta(days=count - index)
            )
            saved_doc.refresh_from_db()
            docs.append(saved_doc)
        return docs

    def activate(self, offering):
        sub = Subscription.objects.create(
            user=self.user,
            product_offering=offering,
            status=Subscription.Status.PENDING,
        )
        sub.activate()
        return sub

    def test_downgrade_locks_oldest_items_and_counts_only_unlocked_items(self):
        docs = self.create_saved_documents(3)
        folders = [
            Folder.objects.create(user=self.user, name="Old"),
            Folder.objects.create(user=self.user, name="New"),
        ]
        searches = [
            SavedSearch.objects.create(user=self.user, q="old"),
            SavedSearch.objects.create(user=self.user, q="new"),
        ]
        follows = [
            UserFollowing.objects.create(
                user=self.user, country=Country.objects.first()
            ),
            UserFollowing.objects.create(user=self.user, court=Court.objects.first()),
        ]
        for items in [folders, searches, follows]:
            for index, item in enumerate(items):
                item.__class__.objects.filter(pk=item.pk).update(
                    created_at=timezone.now() - timedelta(days=2 - index)
                )
                item.refresh_from_db()

        sub = Subscription.objects.create(
            user=self.user,
            product_offering=self.low_offering,
            status=Subscription.Status.ACTIVE,
        )
        reconcile_user_subscription_limits(self.user, sub)

        for item in [docs[0], docs[1], folders[0], searches[0], follows[0]]:
            item.refresh_from_db()
            self.assertTrue(item.is_subscription_locked, item)
            self.assertEqual(
                item.subscription_locked_at.date()
                + timedelta(days=SUBSCRIPTION_LOCK_RETENTION_DAYS),
                item.subscription_lock_expires_at.date(),
            )

        docs[2].refresh_from_db()
        folders[1].refresh_from_db()
        searches[1].refresh_from_db()
        follows[1].refresh_from_db()
        self.assertFalse(docs[2].is_subscription_locked)
        self.assertFalse(folders[1].is_subscription_locked)
        self.assertFalse(searches[1].is_subscription_locked)
        self.assertFalse(follows[1].is_subscription_locked)

        for feature in [
            "saved_document_limit",
            "folder_limit",
            "search_alert_limit",
            "following_limit",
        ]:
            limit_reached, _ = sub.check_feature_limit(feature)
            self.assertTrue(limit_reached)

    def test_locked_items_do_not_count_towards_limits(self):
        saved_doc = self.create_saved_documents(1)[0]
        saved_doc.subscription_locked_at = timezone.now()
        saved_doc.subscription_lock_expires_at = timezone.now() + timedelta(days=60)
        saved_doc.save(
            update_fields=["subscription_locked_at", "subscription_lock_expires_at"]
        )
        sub = Subscription.objects.create(
            user=self.user,
            product_offering=self.low_offering,
            status=Subscription.Status.ACTIVE,
        )

        limit_reached, _ = sub.check_feature_limit("saved_document_limit")

        self.assertFalse(limit_reached)

    def test_upgrade_unlocks_newest_locked_items_first(self):
        docs = self.create_saved_documents(3)
        low_sub = Subscription.objects.create(
            user=self.user,
            product_offering=self.low_offering,
            status=Subscription.Status.ACTIVE,
        )
        reconcile_user_subscription_limits(self.user, low_sub)

        mid_sub = Subscription.objects.create(
            user=self.user,
            product_offering=self.mid_offering,
            status=Subscription.Status.ACTIVE,
        )
        reconcile_user_subscription_limits(self.user, mid_sub)

        for doc in docs:
            doc.refresh_from_db()
        self.assertTrue(docs[0].is_subscription_locked)
        self.assertFalse(docs[1].is_subscription_locked)
        self.assertFalse(docs[2].is_subscription_locked)

    def test_purge_expired_subscription_locked_data(self):
        saved_doc = self.create_saved_documents(1)[0]
        folder = Folder.objects.create(user=self.user, name="Expired empty")
        search = SavedSearch.objects.create(user=self.user, q="expired")
        follow = UserFollowing.objects.create(
            user=self.user, country=Country.objects.first()
        )
        expired_at = timezone.now() - timedelta(days=1)

        for item in [saved_doc, folder, search, follow]:
            item.subscription_locked_at = timezone.now() - timedelta(days=61)
            item.subscription_lock_expires_at = expired_at
            item.save(
                update_fields=["subscription_locked_at", "subscription_lock_expires_at"]
            )

        purge_expired_subscription_locked_data()

        self.assertFalse(SavedDocument.objects.filter(pk=saved_doc.pk).exists())
        self.assertFalse(Folder.objects.filter(pk=folder.pk).exists())
        self.assertFalse(SavedSearch.objects.filter(pk=search.pk).exists())
        self.assertFalse(UserFollowing.objects.filter(pk=follow.pk).exists())
