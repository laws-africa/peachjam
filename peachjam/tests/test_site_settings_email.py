from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings

from peachjam.models import PeachJamSettings


class SiteSettingsEmailTests(SimpleTestCase):
    def test_contact_email_has_default_and_is_required(self):
        self.assertEqual(PeachJamSettings().contact_email, "info@laws.africa")
        field = PeachJamSettings._meta.get_field("contact_email")
        for value in [None, "", "invalid"]:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                field.clean(value, None)
        self.assertEqual(
            field.clean("contact@example.com", None), "contact@example.com"
        )

    @override_settings(ADMINS=[("Admin", "admin@example.com")])
    def test_internal_recipients_and_contact_form_copies(self):
        site = PeachJamSettings(admin_emails="team@example.com\n admin@example.com\t")
        self.assertEqual(
            site.get_admin_emails(), ["team@example.com", "admin@example.com"]
        )
        self.assertEqual(
            site.get_admin_emails(include_defaults=True),
            ["admin@example.com", "team@example.com"],
        )
        site.admin_emails = " \n "
        self.assertEqual(site.get_admin_emails(), ["admin@example.com"])
