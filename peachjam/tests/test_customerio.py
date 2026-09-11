from unittest.mock import call, patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from peachjam.customerio import CustomerIO
from peachjam.models import Court, SavedDocument, UserFollowing, Work
from peachjam_search.models import SavedSearch

User = get_user_model()


class CustomerIOUserDetailsTest(TestCase):
    fixtures = [
        "tests/countries",
        "tests/languages",
        "tests/users",
        "documents/sample_documents",
    ]

    def test_user_details_include_my_lii_counts(self):
        user = User.objects.first()
        saved_document = SavedDocument.objects.create(
            user=user, work=Work.objects.first()
        )
        SavedSearch.objects.create(user=user, q="constitution", filters="")
        UserFollowing.objects.create(user=user, court=Court.objects.first())

        details = CustomerIO().get_user_details(user)

        self.assertEqual(1, details["saved_document_count"])
        self.assertEqual(1, details["saved_search_count"])
        self.assertEqual(1, details["following_count"])
        self.assertEqual(3, user.following.count())

        saved_document.delete()
        details = CustomerIO().get_user_details(user)
        self.assertEqual(0, details["saved_document_count"])

    @patch("peachjam.signals.get_customerio")
    def test_my_lii_deletions_refresh_customerio_user_details(self, get_customerio):
        user = User.objects.first()
        customerio = get_customerio.return_value

        saved_search = SavedSearch.objects.create(
            user=user, q="constitution", filters=""
        )
        saved_search.delete()
        customerio.update_user_details.assert_called_with(user)

        customerio.update_user_details.reset_mock()
        following = UserFollowing.objects.create(user=user, court=Court.objects.first())
        following.delete()
        customerio.update_user_details.assert_called_with(user)

    @patch("peachjam.signals.get_customerio")
    @patch("peachjam.customerio.analytics.track")
    @patch.object(CustomerIO, "enabled", return_value=True)
    @patch.object(CustomerIO, "update_user_details")
    def test_my_lii_tracking_refreshes_customerio_user_details(
        self, update_user_details, enabled, analytics_track, signal_customerio
    ):
        user = User.objects.first()
        saved_document = SavedDocument.objects.create(
            user=user, work=Work.objects.first()
        )
        saved_search = SavedSearch.objects.create(
            user=user, q="constitution", filters=""
        )
        following = UserFollowing.objects.create(user=user, court=Court.objects.first())

        customerio = CustomerIO()
        customerio.track_saved_document(saved_document)
        customerio.track_saved_search(saved_search)
        customerio.track_follow(following)

        self.assertEqual(
            [call(user), call(user), call(user)], update_user_details.call_args_list
        )
