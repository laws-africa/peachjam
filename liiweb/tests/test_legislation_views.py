from datetime import date

from django.test import TestCase, override_settings
from django.urls.base import reverse
from languages_plus.models import Language

from peachjam.models import Legislation


@override_settings(ROOT_URLCONF="liiweb.urls")
class LegislationViewsTest(TestCase):
    fixtures = ["tests/countries", "tests/languages", "documents/sample_documents"]

    def test_legislation_listing_national_only(self):
        response = self.client.get(reverse("legislation_list_all"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["KEY_LINK_PAGE"], "legislation_list")

        self.assertEqual(
            ["D", "Divorce Act, 1979"],
            [doc.title for doc in response.context.get("documents")],
        )

    def test_legislation_listing_filters_subsidiary_expressions_by_language(self):
        parent = (
            Legislation.objects.filter(title="Divorce Act, 1979")
            .order_by("-date")
            .first()
        )
        parent.principal = True
        parent.save(update_fields=["principal"])
        french_parent = Legislation.objects.create(
            jurisdiction=parent.jurisdiction,
            frbr_uri_doctype=parent.frbr_uri_doctype,
            frbr_uri_date=parent.frbr_uri_date,
            frbr_uri_number=parent.frbr_uri_number,
            title=parent.title,
            date=parent.date,
            language=Language.objects.get(pk="fr"),
            principal=True,
            metadata_json=parent.metadata_json,
            published=True,
        )
        self.assertEqual(parent.work_id, french_parent.work_id)

        child_fields = {
            "jurisdiction": parent.jurisdiction,
            "parent_work": parent.work,
            "frbr_uri_doctype": "act",
            "frbr_uri_date": "2020",
            "frbr_uri_number": "language-filter-subsidiary",
            "title": "Language filter subsidiary",
            "principal": True,
            "metadata_json": {"principal": True},
            "published": True,
        }
        english_child = Legislation.objects.create(
            **child_fields,
            date=date(2021, 1, 1),
            language=Language.objects.get(pk="en"),
        )
        french_child = Legislation.objects.create(
            **child_fields,
            date=date(2020, 1, 1),
            language=Language.objects.get(pk="fr"),
        )
        self.assertEqual(english_child.work_id, french_child.work_id)

        response = self.client.get(reverse("legislation_list"), {"languages": "fr"})
        self.assertEqual(response.status_code, 200)
        listed_parent = next(
            doc
            for doc in response.context["documents"]
            if getattr(doc, "pk", None) == french_parent.pk
        )
        self.assertIn(french_child, listed_parent.children)
        self.assertNotIn(english_child, listed_parent.children)

        default_response = self.client.get(reverse("legislation_list"))
        default_parent = next(
            doc
            for doc in default_response.context["documents"]
            if getattr(doc, "pk", None) == parent.pk
        )
        self.assertIn(english_child, default_parent.children)
        self.assertNotIn(french_child, default_parent.children)
