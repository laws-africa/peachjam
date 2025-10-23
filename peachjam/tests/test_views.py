import datetime

from countries_plus.models import Country
from django.conf import settings
from django.contrib.auth.models import Permission, User
from django.core.cache import caches
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse
from languages_plus.models import Language

from peachjam.models import (
    CaseHistory,
    CoreDocument,
    Court,
    Judgment,
    Outcome,
    PeachJamSettings,
    SourceFile,
)
from peachjam.views.robots import (
    _language_prefixes,
    _place_codes,
    _prefixed_place_rules,
)


class PeachjamViewsTest(TestCase):
    fixtures = ["tests/countries", "documents/sample_documents", "tests/users"]

    def test_login_page(self):
        response = self.client.get(reverse("account_login"))
        self.assertTemplateUsed(response, "account/login.html")

    def test_homepage(self):
        response = self.client.get(reverse("home_page"))
        self.assertEqual(response.status_code, 200)

        recent_judgments = [
            r_j.title for r_j in response.context.get("recent_judgments")
        ]
        self.assertIn(
            "Obi vs Federal Republic of Nigeria [2016] ECOWASCJ 52 (09 November 2016)",
            recent_judgments,
        )

        recent_documents = [
            r_d.title for r_d in response.context.get("recent_documents")
        ]
        self.assertIn(
            "Activity Report of the Pan-African Parliament, July 2016 to June 2017",
            recent_documents,
        )

    def test_judgment_listing(self):
        response = self.client.get(reverse("judgment_list"))
        self.assertEqual(response.status_code, 200)

        documents = [doc.title for doc in response.context.get("documents")]
        court_classes = [
            court_class.name for court_class in response.context.get("court_classes")
        ]

        self.assertIn(
            "Ababacar and Ors vs Senegal [2018] ECOWASCJ 17 (29 June 2018)",
            documents,
        )
        self.assertIn("High Court", court_classes)

    def test_court_listing(self):
        response = self.client.get(reverse("court", kwargs={"code": "ECOWASCJ"}))
        self.assertEqual(response.status_code, 200)

        documents = [doc.title for doc in response.context.get("documents")]
        self.assertIn(
            "Ababacar and Ors vs Senegal [2018] ECOWASCJ 17 (29 June 2018)",
            documents,
        )
        self.assertContains(response, "/judgments/ECOWASCJ/2018/")
        self.assertContains(response, "/judgments/ECOWASCJ/2016/")
        self.assertNotIn("years", response.context["facet_data"], [2016, 2018])

    def test_court_year_listing(self):
        response = self.client.get(
            reverse("court_year", kwargs={"code": "ECOWASCJ", "year": 2016})
        )
        self.assertEqual(response.status_code, 200)

        documents = [doc.title for doc in response.context.get("documents")]

        self.assertIn(
            "Obi vs Federal Republic of Nigeria [2016] ECOWASCJ 52 (09 November 2016)",
            documents,
        )
        self.assertNotIn(
            "Ababacar and Ors vs Senegal [2018] ECOWASCJ 17 (29 June 2018)",
            documents,
        )
        self.assertEqual(response.context["year"], 2016)
        self.assertContains(response, "/judgments/ECOWASCJ/2018/")
        self.assertContains(response, "/judgments/ECOWASCJ/2016/")
        self.assertNotIn("years", response.context["facet_data"], [2016, 2018])

    def test_court_year_listing_bad_year(self):
        self.assertEqual(
            self.client.get(
                reverse("court_year", kwargs={"code": "ECOWASCJ", "year": 0})
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                reverse("court_year", kwargs={"code": "ECOWASCJ", "year": 9999999})
            ).status_code,
            404,
        )

    def test_all_judgments_listing(self):
        response = self.client.get(reverse("court", kwargs={"code": "all"}))
        self.assertEqual(response.status_code, 200)

        documents = [doc.title for doc in response.context.get("documents")]
        self.assertIn(
            "Ababacar and Ors vs Senegal [2018] ECOWASCJ 17 (29 June 2018)",
            documents,
        )
        self.assertContains(response, "/judgments/all/2018/")
        self.assertContains(response, "/judgments/all/2016/")
        self.assertNotIn("years", response.context["facet_data"], [2016, 2018])

    @override_settings(
        DEBUG=False,
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            }
        },
        CACHE_MIDDLEWARE_SECONDS=60,
        CACHE_MIDDLEWARE_ALIAS="default",
        CACHE_MIDDLEWARE_KEY_PREFIX="test",
    )
    def test_homepage_cache_control_respects_nocache_query_param(self):
        try:
            response = self.client.get(reverse("home_page"))
            cache_control = response.headers.get("Cache-Control", "")
            self.assertIn("public", cache_control)

            response = self.client.get(reverse("home_page"), {"nocache": "1"})
            cache_control = response.headers.get("Cache-Control", "")
            self.assertNotIn("public", cache_control)
        finally:
            caches["default"].clear()

    def test_all_judgments_year_listing(self):
        response = self.client.get(
            reverse("court_year", kwargs={"code": "all", "year": 2016})
        )
        self.assertEqual(response.status_code, 200)

        documents = [doc.title for doc in response.context.get("documents")]

        self.assertIn(
            "Obi vs Federal Republic of Nigeria [2016] ECOWASCJ 52 (09 November 2016)",
            documents,
        )
        self.assertNotIn(
            "Ababacar and Ors vs Senegal [2018] ECOWASCJ 17 (29 June 2018)",
            documents,
        )
        self.assertEqual(response.context["year"], 2016)
        self.assertContains(response, "/judgments/all/2018/")
        self.assertContains(response, "/judgments/all/2016/")
        self.assertNotIn("years", response.context["facet_data"], [2016, 2018])

    def test_judgment_detail(self):
        response = self.client.get(
            reverse(
                "document_detail",
                kwargs={
                    "frbr_uri": "akn/aa-au/judgment/ecowascj/2018/17/eng@2018-06-29"
                },
            )
        )
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.context["document"].doc_type, "judgment")
        self.assertEqual(
            response.context["document"].expression_frbr_uri,
            "/akn/aa-au/judgment/ecowascj/2018/17/eng@2018-06-29",
        )
        self.assertTrue(hasattr(response.context["document"], "court"))

    def test_legislation_listing(self):
        response = self.client.get(reverse("legislation_list"))
        self.assertEqual(response.status_code, 200)

        documents = [doc.title for doc in response.context.get("documents")]
        self.assertIn(
            "African Civil Aviation Commission Constitution (AFCAC)",
            documents,
        )
        self.assertEqual(
            [("1969", "1969"), ("1979", "1979"), ("2005", "2005")],
            sorted(response.context["facet_data"]["years"]["options"]),
        )

    def test_legislation_detail(self):
        response = self.client.get(
            reverse(
                "document_detail",
                kwargs={
                    "frbr_uri": "akn/aa-au/act/pact/2005/non-aggression-and-common-defence/eng@2005-01-31"
                },
            )
        )
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.context["document"].doc_type, "legislation")
        self.assertEqual(
            response.context["document"].expression_frbr_uri,
            "/akn/aa-au/act/pact/2005/non-aggression-and-common-defence/eng@2005-01-31",
        )
        self.assertTrue(hasattr(response.context["document"], "repealed"))

    def test_generic_document_listing(self):
        response = self.client.get(reverse("generic_document_list"))
        self.assertEqual(response.status_code, 200)

        documents = [doc.title for doc in response.context.get("documents")]
        self.assertIn(
            "Activity Report of the Pan-African Parliament, July 2016 to June 2017",
            documents,
        )
        self.assertEqual(
            [("2017", 2017)],
            response.context["facet_data"]["years"]["options"],
        )

    def test_generic_document_detail(self):
        response = self.client.get(
            reverse(
                "document_detail",
                kwargs={
                    "frbr_uri": "akn/aa-au/doc/activity-report/2017/nn/eng@2017-07-03"
                },
            )
        )
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.context["document"].doc_type, "generic_document")
        self.assertEqual(
            response.context["document"].expression_frbr_uri,
            "/akn/aa-au/doc/activity-report/2017/nn/eng@2017-07-03",
        )
        self.assertTrue(hasattr(response.context["document"], "author"))

    def test_generic_document_detail_unpublished(self):
        doc = CoreDocument.objects.get(
            expression_frbr_uri="/akn/aa-au/doc/activity-report/2017/nn/eng@2017-07-03"
        )
        doc.published = False
        doc.save()
        response = self.client.get(doc.get_absolute_url())
        self.assertEqual(response.status_code, 404)

    def test_generic_document_detail_restricted(self):
        doc = CoreDocument.objects.get(
            expression_frbr_uri="/akn/aa-au/doc/activity-report/2017/nn/eng@2017-07-03"
        )
        doc.restricted = True
        doc.save()
        response = self.client.get(doc.get_absolute_url())
        self.assertEqual(response.status_code, 403)

    def test_robots_txt(self):
        site_settings = PeachJamSettings.load()
        site_settings.robots_txt = None
        site_settings.save()

        blocked_document = CoreDocument.objects.filter(allow_robots=False).first()
        if not blocked_document:
            blocked_document = CoreDocument.objects.first()
            blocked_document.allow_robots = False
            blocked_document.save()

        response = self.client.get("/robots.txt")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "User-agent")
        self.assertNotContains(response, "None")

        body = response.content.decode()
        self.assertIn("Disallow: /search/", body)

        for code, _ in settings.LANGUAGES:
            self.assertIn(f"Disallow: /{code}/search/", body)

        prefixes = _language_prefixes()
        for prefix in prefixes:
            self.assertIn(
                f"Disallow: {prefix}{blocked_document.work_frbr_uri}/", body
            )

        place_rules = _prefixed_place_rules(
            prefixes, _place_codes(site_settings)
        )
        for rule in place_rules:
            self.assertIn(rule, body)

        site_settings.robots_txt = "foo\nbar"
        site_settings.save()

        response = self.client.get("/robots.txt")
        self.assertContains(response, "foo\nbar")

    def test_account_profile(self):
        response = self.client.get(reverse("my_account"))
        self.assertEqual(response.status_code, 302)

        # now log in and try again
        self.client._login(
            User.objects.first(), "django.contrib.auth.backends.ModelBackend"
        )
        response = self.client.get(reverse("my_account"))
        self.assertEqual(response.status_code, 200)

    def test_case_history(self):
        self.user = User.objects.first()
        self.client._login(self.user, "django.contrib.auth.backends.ModelBackend")
        self.user.user_permissions.add(
            Permission.objects.get(codename="can_view_case_history")
        )

        appeal_allowed = Outcome.objects.create(name="Appeal Allowed")

        main_case = Judgment.objects.create(
            case_name="Main case",
            jurisdiction=Country.objects.first(),
            court=Court.objects.first(),
            date=datetime.date(2025, 1, 1),
            language=Language.objects.first(),
        )

        appeal_case = Judgment.objects.create(
            case_name="Appeal case",
            jurisdiction=Country.objects.first(),
            court=Court.objects.first(),
            date=datetime.date(2025, 2, 2),
            language=Language.objects.first(),
        )

        CaseHistory.objects.create(
            judgment_work=appeal_case.work,
            historical_judgment_work=main_case.work,
            outcome=appeal_allowed,
        )

        response = self.client.get(
            reverse(
                "document_case_histories", args=[appeal_case.expression_frbr_uri[1:]]
            )
        )
        self.assertContains(response, "Case history")
        self.assertContains(response, main_case.title)
        self.assertContains(response, appeal_allowed.name)

        response = self.client.get(
            reverse("document_case_histories", args=[main_case.expression_frbr_uri[1:]])
        )
        self.assertContains(response, "reviewed by another court")
        self.assertContains(response, "Case history")
        self.assertContains(response, appeal_case.title)
        self.assertContains(response, appeal_allowed.name)

    def test_document_source_file(self):
        frbr_uri = "/akn/aa-au/judgment/ecowascj/2016/52/eng@2016-11-09"
        doc = CoreDocument.objects.get(expression_frbr_uri=frbr_uri)

        # no source file
        self.assertEqual(
            self.client.get(f"{doc.get_absolute_url()}/source").status_code, 404
        )
        self.assertEqual(
            self.client.get(f"{doc.get_absolute_url()}/source.pdf").status_code, 404
        )

        # basic source file
        sf = SourceFile.objects.create(
            document=doc,
            file=ContentFile(b"test", name="test.txt"),
            mimetype="text/plain",
        )
        resp = self.client.get(f"{doc.get_absolute_url()}/source")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            self.client.get(f"{doc.get_absolute_url()}/source.pdf").status_code, 404
        )
        doc.published = True
        doc.save()

        # pdf source file
        sf.delete()
        sf = SourceFile.objects.create(
            document=doc,
            file=ContentFile(b"test", name="test.pdf"),
            mimetype="application/pdf",
        )
        self.assertEqual(
            self.client.get(f"{doc.get_absolute_url()}/source").status_code, 302
        )
        resp = self.client.get(f"{doc.get_absolute_url()}/source.pdf")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, b"test")

    def test_document_source_unpublished(self):
        frbr_uri = "/akn/aa-au/judgment/ecowascj/2016/52/eng@2016-11-09"
        doc = CoreDocument.objects.get(expression_frbr_uri=frbr_uri)
        doc.published = False
        doc.save()

        # basic source file
        sf = SourceFile.objects.create(
            document=doc,
            file=ContentFile(b"test", name="test.txt"),
            mimetype="text/plain",
        )
        self.assertEqual(
            self.client.get(f"{doc.get_absolute_url()}/source").status_code, 404
        )
        self.assertEqual(
            self.client.get(f"{doc.get_absolute_url()}/source.pdf").status_code, 404
        )

        # pdf source file
        sf.delete()
        sf = SourceFile.objects.create(
            document=doc,
            file=ContentFile(b"test", name="test.pdf"),
            mimetype="application/pdf",
            source_url="https://example.com",
        )
        self.assertEqual(
            self.client.get(f"{doc.get_absolute_url()}/source").status_code, 404
        )
        self.assertEqual(
            self.client.get(f"{doc.get_absolute_url()}/source.pdf").status_code, 404
        )

    def test_document_source_restricted(self):
        frbr_uri = "/akn/aa-au/judgment/ecowascj/2016/52/eng@2016-11-09"
        doc = CoreDocument.objects.get(expression_frbr_uri=frbr_uri)
        doc.restricted = True
        doc.save()

        # basic source file
        sf = SourceFile.objects.create(
            document=doc,
            file=ContentFile(b"test", name="test.txt"),
            mimetype="text/plain",
        )
        self.assertEqual(
            self.client.get(f"{doc.get_absolute_url()}/source").status_code, 404
        )
        self.assertEqual(
            self.client.get(f"{doc.get_absolute_url()}/source.pdf").status_code, 404
        )

        # pdf source file
        sf.delete()
        sf = SourceFile.objects.create(
            document=doc,
            file=ContentFile(b"test", name="test.pdf"),
            mimetype="application/pdf",
            source_url="https://example.com",
        )
        self.assertEqual(
            self.client.get(f"{doc.get_absolute_url()}/source").status_code, 404
        )
        self.assertEqual(
            self.client.get(f"{doc.get_absolute_url()}/source.pdf").status_code, 404
        )

    def test_document_source_file_url(self):
        frbr_uri = "/akn/aa-au/judgment/ecowascj/2016/52/eng@2016-11-09"
        doc = CoreDocument.objects.get(expression_frbr_uri=frbr_uri)

        sf = SourceFile.objects.create(
            document=doc,
            file=ContentFile(b"test", name="test.txt"),
            mimetype="text/plain",
            source_url="https://example.com",
        )
        resp = self.client.get(f"{doc.get_absolute_url()}/source")
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, "https://example.com", fetch_redirect_response=False)
        self.assertEqual(
            self.client.get(f"{doc.get_absolute_url()}/source.pdf").status_code, 404
        )

        sf.delete()
        sf = SourceFile.objects.create(
            document=doc,
            file=ContentFile(b"test", name="test.pdf"),
            mimetype="application/pdf",
            source_url="https://example.com",
        )
        resp = self.client.get(f"{doc.get_absolute_url()}/source")
        self.assertRedirects(
            resp, f"{doc.get_absolute_url()}/source.pdf", fetch_redirect_response=False
        )

        resp = self.client.get(f"{doc.get_absolute_url()}/source.pdf")
        self.assertRedirects(resp, "https://example.com", fetch_redirect_response=False)

    def test_document_source_file_anonymised(self):
        frbr_uri = "/akn/aa-au/judgment/ecowascj/2016/52/eng@2016-11-09"
        doc = CoreDocument.objects.get(expression_frbr_uri=frbr_uri)
        doc.anonymised = True
        doc.save()

        sf = SourceFile.objects.create(
            document=doc,
            file=ContentFile(b"test", name="test.txt"),
            mimetype="text/plain",
        )
        # source file not anonymised
        self.assertEqual(
            self.client.get(f"{doc.get_absolute_url()}/source").status_code, 404
        )
        self.assertEqual(
            self.client.get(f"{doc.get_absolute_url()}/source.pdf").status_code, 404
        )

        # source file is anonymised
        sf.file_is_anonymised = True
        sf.save()
        self.assertEqual(
            self.client.get(f"{doc.get_absolute_url()}/source").status_code, 200
        )

        # pdf source file is anonymised
        sf.delete()
        sf = SourceFile.objects.create(
            document=doc,
            file=ContentFile(b"test", name="test.pdf"),
            mimetype="application/pdf",
            file_is_anonymised=True,
        )
        resp = self.client.get(f"{doc.get_absolute_url()}/source")
        self.assertRedirects(
            resp, f"{doc.get_absolute_url()}/source.pdf", fetch_redirect_response=False
        )
        self.assertEqual(
            self.client.get(f"{doc.get_absolute_url()}/source.pdf").status_code, 200
        )

        # extra anonymised file is available
        sf.delete()
        sf = SourceFile.objects.create(
            document=doc,
            file=ContentFile(b"test", name="test.txt"),
            mimetype="text/plain",
            anonymised_file_as_pdf=ContentFile(b"anon", name="anon.pdf"),
        )
        resp = self.client.get(f"{doc.get_absolute_url()}/source")
        self.assertRedirects(
            resp, f"{doc.get_absolute_url()}/source.pdf", fetch_redirect_response=False
        )
        resp = self.client.get(f"{doc.get_absolute_url()}/source.pdf")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, b"anon")
