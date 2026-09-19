from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.urls.base import reverse
from django.utils import timezone

from peachjam.models import (
    DocumentNature,
    DocumentTopic,
    Legislation,
    Locality,
    PeachJamSettings,
    PopularLegislation,
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
        self.assertNotContains(response, "View all popular legislation")
        self.assertNotContains(response, "bi-arrow-right")
        self.assertNotContains(response, 'data-component="DocumentList"')
        self.assertEqual([], list(response.context["documents"]))
        self.assertIsNone(response.context["paginator"])
        self.assertEqual([], response.context["popular_legislation"])
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

        listing_response = self.client.get(
            reverse("locality_legislation_list", args=[locality.place_code()])
        )
        self.assertContains(listing_response, 'class="nav nav-tabs')

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
        self.assertContains(response, "Current legislation")
        self.assertContains(response, "Principal legislation currently in force.")
        self.assertNotContains(response, "More resources")
        self.assertNotContains(response, 'class="nav nav-tabs')

    def test_legislation_listing_page_shows_only_selected_variant(self):
        response = self.client.get(reverse("legislation_list_recent"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Recent legislation")
        self.assertContains(response, "Legislation published in the past year.")
        self.assertNotContains(response, "Current legislation")
        self.assertNotContains(response, "Popular legislation")
        self.assertNotContains(response, "More resources")
        self.assertNotContains(response, 'action="/search/"')

    def test_popular_legislation_section_uses_admin_order(self):
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

        PopularLegislation.objects.create(work=constitution.work, position=2)
        PopularLegislation.objects.create(work=highly_ranked.work, position=1)

        landing_response = self.client.get(
            reverse("legislation_list"), {"nocache": "1"}
        )

        self.assertEqual(
            [highly_ranked.pk, constitution.pk],
            [
                document.pk
                for document in landing_response.context["popular_legislation"]
            ],
        )
        self.assertNotEqual(
            constitution.pk,
            landing_response.context["popular_legislation"][0].pk,
        )

    def test_popular_legislation_suggestions_preserve_admin_choices(self):
        existing = Legislation.objects.get(pk=3040)
        site_settings = PeachJamSettings.load()
        site_settings.default_document_jurisdiction = existing.jurisdiction
        site_settings.save()
        suggested = Legislation.objects.create(
            jurisdiction=existing.jurisdiction,
            frbr_uri_doctype="act",
            frbr_uri_date="2025",
            frbr_uri_number="999",
            title="Suggested Act, 2025",
            date=timezone.now().date(),
            language=existing.language,
            metadata_json={},
            principal=True,
        )
        suggested.work.authority_score = 1
        suggested.work.pagerank = 1
        suggested.work.save(update_fields=["authority_score", "pagerank"])
        curated = PopularLegislation.objects.create(work=existing.work, position=5)

        call_command("suggest_popular_legislation", limit=2, stdout=StringIO())
        call_command("suggest_popular_legislation", limit=2, stdout=StringIO())

        curated.refresh_from_db()
        self.assertEqual(5, curated.position)
        self.assertEqual(
            [existing.work_id, suggested.work_id],
            list(
                PopularLegislation.objects.order_by("position").values_list(
                    "work_id", flat=True
                )
            ),
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
