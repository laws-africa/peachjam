from datetime import date
from io import StringIO

from bs4 import BeautifulSoup
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls.base import reverse
from django.utils import timezone
from languages_plus.models import Language

from peachjam.models import (
    DocumentNature,
    DocumentTopic,
    EntityProfile,
    JurisdictionProfile,
    Legislation,
    Locality,
    PeachJamSettings,
    PopularLegislation,
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
        soup = BeautifulSoup(response.content, "html.parser")
        search_form = soup.find("form", action=reverse("legislation_list_all"))
        search_button = search_form.find("button", type="submit")
        self.assertEqual("Search", search_button.get_text(strip=True))
        self.assertIsNone(search_button.find("i"))
        self.assertContains(response, "Browse by year")
        self.assertContains(response, "Current legislation")
        self.assertNotContains(response, "Local legislation")
        self.assertNotContains(response, "Browse by legal topic")
        self.assertContains(response, "Document nature")
        self.assertContains(
            response,
            f"{reverse('legislation_list_all')}?years="
            f"{response.context['legislation_years'][0]}",
        )
        self.assertContains(response, "Legislation that is not currently in force")
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
            f"{reverse('legislation_list_all')}?taxonomies={topic.slug}",
        )

    def test_landing_page_links_to_document_nature_filter(self):
        document = Legislation.objects.get(pk=3040)
        nature = DocumentNature.objects.get(name="Act")
        document.nature = nature
        document.save(update_fields=["nature"])

        response = self.client.get(reverse("legislation_list"), {"nocache": "1"})

        self.assertContains(
            response,
            f"{reverse('legislation_list_all')}?natures={nature.code}",
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

    def test_legislation_listing_ignores_empty_nature_filter(self):
        response = self.client.get(reverse("legislation_list_all"), {"natures": ""})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            ["D", "Divorce Act, 1979"],
            [document.title for document in response.context["documents"]],
        )

    def test_variant_listing_uses_variant_heading_and_breadcrumbs(self):
        jurisdiction = Legislation.objects.get(pk=3040).jurisdiction
        site_settings = PeachJamSettings.load()
        site_settings.document_jurisdictions.set([jurisdiction])
        jurisdiction_profile = JurisdictionProfile.objects.create(
            jurisdiction=jurisdiction
        )
        EntityProfile.objects.create(
            content_object=jurisdiction_profile,
            title="National Legislation",
        )

        for url_name, heading in [
            ("legislation_list_recent", "Recent legislation"),
            ("legislation_list_subsidiary", site_settings.subleg_label),
        ]:
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))

                self.assertEqual(response.status_code, 200)
                soup = BeautifulSoup(response.content, "html.parser")
                self.assertTrue(
                    soup.title.get_text(" ", strip=True).startswith(heading)
                )
                self.assertEqual(
                    heading,
                    soup.find("h1", id="main-page-heading").get_text(strip=True),
                )
                breadcrumb = soup.find("nav", attrs={"aria-label": "breadcrumb"})
                self.assertIsNotNone(breadcrumb)
                self.assertEqual(
                    heading,
                    breadcrumb.find("li", class_="active").get_text(strip=True),
                )
                self.assertNotContains(response, "National Legislation")

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

        default_response = self.client.get(reverse("legislation_list_current"))
        default_parent = next(
            doc
            for doc in default_response.context["documents"]
            if getattr(doc, "pk", None) == parent.pk
        )
        self.assertIn(english_child, default_parent.children)
        self.assertNotIn(french_child, default_parent.children)
