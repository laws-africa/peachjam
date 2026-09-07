from django.test import TestCase
from django.urls.base import reverse
from django.utils import timezone

from peachjam.models import (
    DocumentNature,
    DocumentTopic,
    Legislation,
    Locality,
    PeachJamSettings,
    Taxonomy,
)


class LegislationViewsTest(TestCase):
    fixtures = ["tests/countries", "documents/sample_documents"]

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
        self.assertNotIn("metadata_json", recent_document.get_deferred_fields())

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

    def test_popular_legislation_order_matches_landing_page(self):
        constitution = Legislation.objects.get(pk=3040)
        constitution.title = "Constitution of Zambia Act, 1991"
        constitution.save(update_fields=["title"])
        constitution.work.authority_score = 0
        constitution.work.pagerank = 0
        constitution.work.save(update_fields=["authority_score", "pagerank"])

        highly_ranked = Legislation.objects.create(
            jurisdiction=constitution.jurisdiction,
            frbr_uri_doctype="act",
            frbr_uri_date="2025",
            frbr_uri_number="999",
            title="Highly Referenced Act, 2025",
            date=timezone.now().date(),
            language=constitution.language,
            metadata_json={},
            principal=True,
        )
        highly_ranked.work.authority_score = 1
        highly_ranked.work.pagerank = 1
        highly_ranked.work.save(update_fields=["authority_score", "pagerank"])

        landing_response = self.client.get(
            reverse("legislation_list"), {"nocache": "1"}
        )
        popular_response = self.client.get(reverse("legislation_list_popular"))

        self.assertEqual(
            constitution.pk,
            landing_response.context["popular_legislation"][0].pk,
        )
        self.assertEqual(
            constitution.pk,
            list(popular_response.context["documents"])[0].pk,
        )

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

    def test_legislation_listing_ignores_non_legislation_nature_filter(self):
        response = self.client.get(
            reverse("legislation_list_all"), {"natures": "judgment"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual([], list(response.context.get("documents")))
