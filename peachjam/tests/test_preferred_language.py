from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.urls import reverse
from languages_plus.models import Language

from peachjam.models import Legislation, UserProfile
from peachjam.signals import set_user_language


class TestPreferredLanguage(TestCase):
    fixtures = ["tests/countries", "documents/sample_documents", "tests/languages"]
    maxDiff = None

    def test_preferred_language(self):
        response = self.client.get(reverse("legislation_list"))
        self.assertEqual(4, response.context.get("documents").count())

    def test_update_work_languages(self):
        doc = Legislation.objects.get(
            expression_frbr_uri="/akn/aa-au/act/1969/civil-aviation-commission/eng@1969-01-17"
        )
        work = doc.work
        work.update_languages()
        self.assertEqual(["eng"], work.languages)

        # create a french copy
        doc2 = Legislation.objects.create(
            jurisdiction=doc.jurisdiction,
            locality=doc.locality,
            frbr_uri_doctype="act",
            frbr_uri_date=doc.frbr_uri_date,
            frbr_uri_number=doc.frbr_uri_number,
            title=doc.title,
            date=doc.date,
            language=Language.objects.get(pk="fr"),
            metadata_json={},
        )
        self.assertNotEqual(doc.pk, doc2.pk)

        work.refresh_from_db()
        self.assertEqual(["eng", "fra"], sorted(work.languages))

        doc2.delete()
        work.refresh_from_db()
        self.assertEqual(["eng"], sorted(work.languages))


class TestSetUserLanguageSignal(TestCase):
    fixtures = ["tests/users", "tests/languages"]

    def test_creates_missing_profile_before_setting_language(self):
        user = User.objects.get(pk=1)
        UserProfile.objects.filter(user=user).delete()
        self.assertFalse(UserProfile.objects.filter(user=user).exists())

        request = RequestFactory().get("/")
        set_user_language(sender=User, request=request, user=user)

        self.assertTrue(UserProfile.objects.filter(user=user).exists())
        self.assertEqual("en", request.set_language)
