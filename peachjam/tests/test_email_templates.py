import re
from types import SimpleNamespace
from unittest.mock import patch

from bs4 import BeautifulSoup
from django.template import Context, Template
from django.template.loader import render_to_string
from django.test import SimpleTestCase
from templated_email import get_templated_mail

from peachjam.emails import TemplateBackend
from peachjam.timeline_email_service import EmailAlert, EmailAlertSummaryItem


class EmailUser:
    first_name = ""
    email = "test@example.org"
    username = "test"

    def get_full_name(self):
        return "Test User"


class EmailTemplateUrlTestCase(SimpleTestCase):
    maxDiff = None

    def base_context(self, domain):
        return {
            "site": SimpleNamespace(domain=domain),
            "user": EmailUser(),
            "APP_NAME": "Peach Jam",
            "MY_LII": "My Peach Jam",
            "PRIMARY_COLOUR": "#123456",
        }

    def get_branded_mail(self, template_name, context):
        backend = TemplateBackend()
        with patch.object(backend, "supplement_context"):
            return backend.get_email_message(
                template_name,
                context,
                from_email="test@example.org",
                to=["user@example.org"],
            )

    def test_branded_email_styles_are_safe_for_email_clients(self):
        context = self.base_context("example.org")
        context["activate_url"] = "https://example.org/accounts/confirm-email/"

        message = self.get_branded_mail(
            "account/email/email_confirmation_signup", context
        )
        html = message.alternatives[0][0]
        soup = BeautifulSoup(html, "html.parser")

        button = soup.find("a", string=re.compile("Confirm your email address"))
        self.assertIn("color: #fefefe", button["style"])
        self.assertIn("padding: 8px 16px", button["style"])
        self.assertIn("background: #123456", button.find_parent("td")["style"])
        self.assertIn(
            "border: 1px solid #dee2e6",
            soup.find("table", class_="inner-container")["style"],
        )
        self.assertIn(
            "background-color: #f8f9fa",
            soup.find("table", class_="body")["style"],
        )

        style_blocks = [style.get_text() for style in soup.find_all("style")]
        self.assertTrue(any("@media" in style for style in style_blocks))
        self.assertTrue(all(len(style.encode()) < 8192 for style in style_blocks))

    def test_account_and_organisation_templates_render_html_and_plain_text(self):
        template_contexts = {
            "account/email/account_already_exists": {
                "email": "test@example.org",
                "password_reset_url": "https://example.org/reset/",
            },
            "account/email/email_changed": {
                "from_email": "old@example.org",
                "to_email": "new@example.org",
            },
            "account/email/email_confirm": {},
            "account/email/email_confirmation": {
                "activate_url": "https://example.org/activate/"
            },
            "account/email/email_confirmation_signup": {
                "activate_url": "https://example.org/activate/"
            },
            "account/email/email_deleted": {"deleted_email": "old@example.org"},
            "account/email/login_code": {"code": "123456"},
            "account/email/password_changed": {},
            "account/email/password_reset": {},
            "account/email/password_reset_key": {
                "password_reset_url": "https://example.org/reset/",
                "username": "test",
            },
            "account/email/password_set": {},
            "account/email/unknown_account": {
                "email": "test@example.org",
                "signup_url": "https://example.org/signup/",
            },
            "organisation/invitation": {
                "organisation": "Example Organisation",
                "expiry": "7 October 2026",
                "invitation_url": "https://example.org/invitation/",
            },
            "organisation/notification": {
                "subject": "Example notification",
                "body": "An example notification body.",
            },
        }

        for template_name, extra_context in template_contexts.items():
            with self.subTest(template_name=template_name):
                context = self.base_context("example.org")
                context.update(extra_context)
                message = self.get_branded_mail(template_name, context)
                html = message.alternatives[0][0]

                self.assertTrue(message.subject)
                self.assertTrue(message.body.strip())
                self.assertIn("Peach Jam", html)
                self.assertIn("style=", html)

    def assert_alert_document_item_spacing(self, html):
        self.assertIn('<li class="alert-document-list-item">', html)
        self.assertIn('<div class="alert-document-flynote">', html)

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

    def test_email_alert_digest_renders_an_email_alert_object(self):
        context = self.base_context("example.org")
        email_alert = EmailAlert(
            user=context["user"],
            summary_items=[
                EmailAlertSummaryItem(
                    label="High Court of Tanzania – 1 new judgment",
                    subject="High Court of Tanzania: 1 new judgment",
                    preheader="1 High Court of Tanzania judgment",
                    priority=1,
                    section_id="followed-documents",
                )
            ],
            summary_more_count=0,
            summary_has_anchor_links=False,
            subject="High Court of Tanzania: 1 new judgment",
            preheader="1 High Court of Tanzania judgment",
            intro="You have 1 update since 25 August 2026.",
            frequency="daily",
            followed_documents=[],
            followed_total=0,
            saved_searches=[],
            searches_total=0,
            citations=[],
            citations_total=0,
            relationships=[],
            relationships_total=0,
            timeline_url_path="/en/my/#timeline",
            manage_url_path="/en/account/",
            displayed_events=[],
        )
        context.update(email_alert.template_context())

        message = self.get_branded_mail("email_alert_digest", context)
        html = message.alternatives[0][0] if message.alternatives else message.body
        summary = BeautifulSoup(html, "html.parser").find(
            "div", class_="digest-summary"
        )

        self.assertEqual("High Court of Tanzania: 1 new judgment", message.subject)
        self.assertIn("Hi there,", html)
        self.assertIn("Here is your daily My Peach Jam update.", html)
        self.assertIn("You have 1 update since 25 August 2026.", html)
        self.assertIn("High Court of Tanzania – 1 new judgment", html)
        self.assertIn("background-color: #f8f9fa", summary["style"])
        self.assertIn("border-left: 3px solid #123456", summary["style"])

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
        self.assertIn(
            "We have found citations for documents that you have saved.",
            html,
        )

    def test_following_alert_email_adds_email_safe_flynote_spacing(self):
        context = self.base_context("example.org")
        context.update(
            {
                "manage_url_path": "/en/my/following/",
                "followed_documents": [
                    {
                        "followed_object": "Civil procedure",
                        "documents": [
                            SimpleNamespace(
                                title="Example document",
                                expression_frbr_uri="/documents/example/",
                                blurb="Short <b>blurb</b>",
                                flynote="First line\nSecond line",
                            )
                        ],
                    }
                ],
            }
        )

        message = get_templated_mail(
            template_name="user_following_alert",
            from_email="test@example.org",
            to=["user@example.org"],
            context=context,
        )
        html = message.alternatives[0][0] if message.alternatives else message.body

        self.assert_alert_document_item_spacing(html)
        self.assertIn("Short &lt;b&gt;blurb&lt;/b&gt;", html)
        self.assertIn("First line<br>Second line", html)

    def test_citation_alert_email_escapes_blurb_markup(self):
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
                                    blurb="Short <b>blurb</b>",
                                    flynote="First line\nSecond line",
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

        self.assert_alert_document_item_spacing(html)
        self.assertIn("Short &lt;b&gt;blurb&lt;/b&gt;", html)
        self.assertIn("First line<br>Second line", html)

    def test_relationship_alert_email_escapes_blurb_markup(self):
        context = self.base_context("example.org")
        context.update(
            {
                "manage_url_path": "/en/my/following/",
                "saved_documents": [
                    {
                        "saved_document": SimpleNamespace(
                            get_absolute_url="/documents/saved/",
                            work=SimpleNamespace(title="Saved document"),
                        ),
                        "relationships": {
                            "new_amendment": {
                                "label": "New amendments published for",
                                "documents": [
                                    SimpleNamespace(
                                        title="Related document",
                                        get_absolute_url="/documents/related/",
                                        blurb="Short <b>blurb</b>",
                                        flynote="First line\nSecond line",
                                    )
                                ],
                            }
                        },
                    }
                ],
            }
        )

        message = get_templated_mail(
            template_name="new_relationship_alert",
            from_email="test@example.org",
            to=["user@example.org"],
            context=context,
        )
        html = message.alternatives[0][0] if message.alternatives else message.body

        self.assert_alert_document_item_spacing(html)
        self.assertIn("Short &lt;b&gt;blurb&lt;/b&gt;", html)
        self.assertIn("First line<br>Second line", html)

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
