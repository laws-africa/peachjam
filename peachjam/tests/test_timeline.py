from datetime import datetime

from countries_plus.models import Country
from django.contrib.auth.models import Permission, User
from django.test import TestCase
from languages_plus.models import Language

from peachjam.models import Court, Judgment, UserFollowing


class TimelineViewTest(TestCase):
    fixtures = ["tests/countries", "documents/sample_documents", "tests/users"]

    def setUp(self):

        self.user = User.objects.first()
        self.client._login(self.user, "django.contrib.auth.backends.ModelBackend")
        self.user.user_permissions.add(
            Permission.objects.get(codename="view_userfollowing")
        )

    def test_timeline_view(self):
        court = Court.objects.get(code="ECOWASCJ")
        follow = UserFollowing.objects.create(user=self.user, court=court)
        follow.last_alerted_at = datetime(2000, 7, 1)
        follow.save()

        UserFollowing.update_timeline(self.user)

        date = datetime(2023, 10, 1)

        Judgment.objects.create(
            case_name="New Case",
            court=court,
            date=date,
            language=Language.objects.get(pk="en"),
            jurisdiction=Country.objects.get(pk="ZA"),
        )

        response = self.client.get("/my/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, "Ababacar and Ors vs Senegal [2018] ECOWASCJ 17 (29 June 2018)"
        )
        self.assertContains(
            response,
            "Obi vs Federal Republic of Nigeria [2016] ECOWASCJ 52 (09 November 2016",
        )
        self.assertNotContains(response, "New Case")

        UserFollowing.update_timeline(self.user)
        response = self.client.get("/my/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "New Case")
