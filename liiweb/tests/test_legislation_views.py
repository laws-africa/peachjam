from datetime import date

from django.test import TestCase, override_settings
from django.urls.base import reverse
from django.utils import timezone
from languages_plus.models import Language

from peachjam.models import (
    DocumentNature,
    DocumentTopic,
    Legislation,
    Locality,
    PeachJamSettings,
    Taxonomy,
)


@override_settings(ROOT_URLCONF="liiweb.urls")
class LegislationViewsTest(TestCase):
    fixtures = ["tests/countries", "tests/languages", "documents/sample_documents"]

    def test_legislation_landing_page(self):
        response = self.client.get(reverse("legislation_list"), {"nocache": "1"})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "liiweb/legislation_landing.html")
        self.assertEqual(1, response.context["legislation_counts"]["total"])
        self.assertContains(response, "Find legislation")
        self.assertContains(response, f'action="{reverse("legislation_list_all")}"')
        self.assertContains(response, 'name="years"')
        self.assertContains(response, 'name="natures"')
        self.assertContains(response, "Browse by year")
        self.assertContains(response, "Current legislation")
        self.assertNotContains(response, "Local legislation")
        self.assertNotContains(response, "Browse by legal topic")
        self.assertContains(response, "Document nature")
        self.assertContains(
            response,
            f'{reverse("legislation_list_all")}?years='
            f'{response.context["legislation_years"][0]}',
        )
        self.assertContains(response, "Legislation by status")
        self.assertContains(response, "Popular legislation")
        self.assertNotContains(response, 'data-component="DocumentList"')
        self.assertEqual([], list(response.context["documents"]))
        self.assertIsNone(response.context["paginator"])
        self.assertEqual(1, len(response.context["popular_legislation"]))
        self.assertEqual(
            404,
            self.client.get(reverse("locality_legislation")).status_code,
        )

    def test_landing_page_shows_local_legislation_when_documents_exist(self):
        locality = Locality.objects.get(pk=1)
        site_settings = PeachJamSettings.load()
        site_settings.default_document_jurisdiction = locality.jurisdiction
        site_settings.save()

        response = self.client.get(reverse("legislation_list"), {"nocache": "1"})

        self.assertContains(response, "Local legislation")
        locality_response = self.client.get(reverse("locality_legislation"))
        self.assertEqual(locality_response.status_code, 200)
        locality_groups = locality_response.context["locality_groups"]
        self.assertEqual(
            [locality], [item for group in locality_groups for item in group]
        )

    def test_landing_page_hides_empty_configured_localities(self):
        locality = Locality.objects.get(pk=1)
        Legislation.objects.filter(locality=locality).delete()
        site_settings = PeachJamSettings.load()
        site_settings.default_document_jurisdiction = locality.jurisdiction
        site_settings.save()

        response = self.client.get(reverse("legislation_list"), {"nocache": "1"})

        self.assertNotContains(response, "Local legislation")

    def test_landing_page_shows_topics_only_when_assigned(self):
        document = Legislation.objects.get(pk=3040)
        topic = Taxonomy.add_root(name="Family law")
        DocumentTopic.objects.create(document=document, topic=topic)

        response = self.client.get(reverse("legislation_list"), {"nocache": "1"})

        self.assertContains(response, "Browse by legal topic")
        self.assertContains(response, "Family law")
        self.assertContains(
            response,
            f'{reverse("legislation_list_all")}?taxonomies={topic.slug}',
        )

    def test_landing_page_links_to_document_nature_filter(self):
        document = Legislation.objects.get(pk=3040)
        nature = DocumentNature.objects.get(name="Act")
        document.nature = nature
        document.save(update_fields=["nature"])

        response = self.client.get(reverse("legislation_list"), {"nocache": "1"})

        self.assertContains(
            response,
            f'{reverse("legislation_list_all")}?natures={nature.code}',
        )

    def test_recent_legislation_displays_its_publication_date(self):
        document = Legislation.objects.get(pk=3040)
        publication_date = timezone.now().date()
        document.metadata_json["publication_date"] = publication_date.isoformat()
        document.save(update_fields=["metadata_json"])

        response = self.client.get(reverse("legislation_list"), {"nocache": "1"})

        recent_document = response.context["recent_legislation"][0]
        self.assertEqual(publication_date, recent_document.landing_publication_date)

    def test_current_legislation_has_its_own_listing_page(self):
        response = self.client.get(reverse("legislation_list_current"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "liiweb/legislation_list.html")
        self.assertContains(response, 'data-component="DocumentList"')

    def test_popular_legislation_has_its_own_listing_page(self):
        response = self.client.get(reverse("legislation_list_popular"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "liiweb/legislation_list.html")
        self.assertContains(response, 'class="nav-link active"')
        self.assertEqual("popular", response.context["form"].cleaned_data["sort"])

    def test_filtered_legacy_landing_url_uses_the_listing_page(self):
        response = self.client.get(reverse("legislation_list"), {"years": "1979"})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "liiweb/legislation_list.html")
        self.assertContains(response, 'data-component="DocumentList"')

    def test_legislation_listing_national_only(self):
        response = self.client.get(reverse("legislation_list_all"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["KEY_LINK_PAGE"], "legislation_list")
        self.assertTemplateUsed(response, "liiweb/legislation_list.html")

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

        response = self.client.get(reverse("legislation_list_all"), {"languages": "fr"})
        self.assertEqual(response.status_code, 200)
        listed_parent = next(
            doc
            for doc in response.context["documents"]
            if getattr(doc, "pk", None) == french_parent.pk
        )
        self.assertIn(french_child, listed_parent.children)
        self.assertNotIn(english_child, listed_parent.children)

        default_response = self.client.get(reverse("legislation_list_all"))
        default_parent = next(
            doc
            for doc in default_response.context["documents"]
            if getattr(doc, "pk", None) == parent.pk
        )
        self.assertIn(english_child, default_parent.children)
        self.assertNotIn(french_child, default_parent.children)

    def test_legislation_listing_ignores_non_legislation_nature_filter(self):
        response = self.client.get(
            reverse("legislation_list_all"), {"natures": "judgment"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual([], list(response.context.get("documents")))
