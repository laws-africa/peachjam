from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django_webtest import WebTest
from guardian.shortcuts import assign_perm

from peachjam.models import Judgment

User = get_user_model()


class DocumentViewTestCase(WebTest):
    fixtures = [
        "tests/countries",
        "tests/courts",
        "tests/languages",
        "documents/sample_documents",
    ]

    def test_document_citation_links(self):
        doc = Judgment.objects.first()
        response = self.app.get(doc.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            '<script id="citation-links" type="application/json">[]</script>',
            html=True,
        )
        self.assertContains(
            response,
            '<script id="provision-relationships" type="application/json">[]</script>',
            html=True,
        )
        self.assertContains(
            response,
            '<script id="provision-enrichments-json" type="application/json">[]</script>',
            html=True,
        )
        self.assertContains(
            response,
            '<script id="incoming-citations-json" type="application/json">[]</script>',
            html=True,
        )


class RestrictedDocumentsTestCase(WebTest):
    fixtures = [
        "tests/users",
        "tests/countries",
        "tests/courts",
        "tests/languages",
        "documents/sample_documents",
    ]

    def setUp(self):
        judgment = Judgment.objects.get(
            expression_frbr_uri="/akn/aa-au/judgment/ecowascj/2018/17/eng@2018-06-29"
        )
        judgment.restricted = True
        judgment.save()

        group = Group.objects.get(name="Officers")
        assign_perm("view_judgment", group, judgment)

    def test_restricted_document_unauthorized(self):
        doc = Judgment.objects.get(
            expression_frbr_uri="/akn/aa-au/judgment/ecowascj/2018/17/eng@2018-06-29"
        )
        unauthorized_user = User.objects.get(username="user@example.com")
        response = self.app.get(
            doc.get_absolute_url(), user=unauthorized_user, expect_errors=True
        )
        self.assertIn("Permission denied", response.text)
        self.assertEqual(response.status_code, 403)

    def test_restricted_document_authorized(self):
        doc = Judgment.objects.get(
            expression_frbr_uri="/akn/aa-au/judgment/ecowascj/2018/17/eng@2018-06-29"
        )
        authorized_user = User.objects.get(username="officer@example.com")
        response = self.app.get(doc.get_absolute_url(), user=authorized_user)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("public", response.headers.get("Cache-Control", ""))
