from types import SimpleNamespace

from django.template import Context, Template
from django.template.loader import render_to_string
from django.test import SimpleTestCase
from templated_email import get_templated_mail


class EmailTemplateUrlTestCase(SimpleTestCase):
    maxDiff = None

    def base_context(self, domain):
        return {
            "site": SimpleNamespace(domain=domain),
            "user": SimpleNamespace(get_full_name="Test User"),
            "APP_NAME": "Peach Jam",
            "PRIMARY_COLOUR": "#123456",
        }

    def test_absolute_url_tag_adds_https_and_preserves_existing_scheme(self):
        template = Template(
            "{% load peachjam %}"
            "{% absolute_url bare '/en/documents/' %}|"
            "{% absolute_url secure '/en/documents/' %}"
        )

        rendered = template.render(
            Context(
                {
                    "bare": SimpleNamespace(domain="example.org"),
                    "secure": SimpleNamespace(domain="https://example.org"),
                }
            )
        )

        self.assertEqual(
            rendered,
            "https://example.org/en/documents/|https://example.org/en/documents/",
        )

    def test_alert_email_templates_render_absolute_links(self):
        context = self.base_context("example.org")
        context.update(
            {
                "manage_url_path": "/en/my/following/",
                "saved_documents": [
                    {
                        "saved_document": SimpleNamespace(
                            title="Saved document",
                            get_absolute_url="/documents/saved/",
                        ),
                        "citing_documents": [
                            {
                                "document": SimpleNamespace(
                                    title="Citing document",
                                    get_absolute_url="/documents/citing/",
                                    blurb="",
                                    flynote="",
                                ),
                                "provision_citations": [],
                            }
                        ],
                    }
                ],
            }
        )

        message = get_templated_mail(
            template_name="new_citation_alert",
            from_email="test@example.org",
            to=["user@example.org"],
            context=context,
        )
        html = message.alternatives[0][0] if message.alternatives else message.body

        self.assertIn(
            'href="https://example.org/en/my/following/?utm_campaign=following&utm_source=alert&utm_medium=email"',
            html,
        )
        self.assertIn(
            'href="https://example.org/en/accounts/profile/"',
            html,
        )
        self.assertIn(
            'src="https://example.org/static/images/logo.png"',
            html,
        )
        self.assertIn(
            'href="https://example.org/documents/saved/?utm_campaign=new_citation&utm_source=alert&utm_medium=email"',
            html,
        )
        self.assertIn(
            'href="https://example.org/documents/citing/?utm_campaign=new_citation&utm_source=alert&utm_medium=email"',
            html,
        )

    def test_search_alert_email_does_not_duplicate_protocol(self):
        context = self.base_context("https://example.org")
        context.update(
            {
                "manage_url_path": "/en/search/saved-searches/",
                "saved_search": SimpleNamespace(
                    q="example query",
                    get_absolute_url="/en/search/?q=example",
                    pretty_filters="",
                ),
                "hits": [
                    {
                        "expression_frbr_uri": "/documents/hit/",
                        "document": SimpleNamespace(
                            title="Hit title",
                            blurb="",
                            flynote="",
                        ),
                        "highlight": {},
                        "pages": [
                            {"page_num": 3, "highlight": {"pages.body": ["Example"]}}
                        ],
                        "provisions": [],
                    }
                ],
            }
        )

        html = render_to_string(
            "peachjam/emails/search_alert.email",
            context=context,
        )

        self.assertNotIn("https://https://example.org", html)
        self.assertIn('href="https://example.org/en/search/?q=example"', html)
        self.assertIn('href="https://example.org/documents/hit/"', html)
        self.assertIn('href="https://example.org/documents/hit/#page-3"', html)
