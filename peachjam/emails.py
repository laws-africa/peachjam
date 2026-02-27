import logging

import css_inline
from customerio import APIClient, Regions, SendEmailRequest
from django.conf import settings
from django.contrib.sites.models import Site
from django.contrib.staticfiles import finders
from templated_email.backends.vanilla_django import (
    TemplateBackend as BaseTemplateBackend,
)

log = logging.getLogger(__name__)


class TemplateBackend(BaseTemplateBackend):
    primary_colour = None

    def supplement_context(self, context):
        # inject common context
        context["site"] = Site.objects.get_current()
        context["APP_NAME"] = settings.PEACHJAM["APP_NAME"]
        context["PRIMARY_COLOUR"] = self.get_primary_colour()

    def _render_email(
        self, template_name, context, template_dir=None, file_extension=None
    ):
        self.supplement_context(context)

        parts = super()._render_email(
            template_name,
            context,
            template_dir=template_dir,
            file_extension=file_extension,
        )

        if parts.get("html"):
            # inline CSS styles into the HTML
            parts["html"] = css_inline.inline(parts["html"])

        return parts

    def get_primary_colour(self):
        if self.primary_colour is None:
            # try to get the primary colour from the _variables.scss file, looked up using the static files finder
            path = finders.find("stylesheets/_variables.scss")
            if path:
                print(f"Found _variables.scss at {path}")
                with open(path, "r") as f:
                    for line in f:
                        if line.startswith("$primary:"):
                            self.__class__.primary_colour = (
                                line.split(":", 1)[1].strip().rstrip(";")
                            )
                            break

        return (
            self.primary_colour or settings.PEACHJAM.get("PRIMARY_COLOUR") or "#0000ff"
        )


class CustomerIOTemplateBackend(TemplateBackend):
    """Sends emails using CustomerIO if enabled, falling back to the usual Django email system otherwise.

    The rendering is always done using Django templates, but for certain templates the rendered context is sent to
    CustomerIO to send the email instead of using Django's email system. This allows us to use CustomerIO's
    transactional messaging features, such as automatically retrying failed emails and tracking opens and clicks.
    """

    # use CustomerIO for these templates, otherwise send using Django's email system
    transactional_templates = [
        "search_alert",
        "user_following_alert",
        "new_citation_alert",
        "new_relationship_alert",
        "new_overturn_alert",
        "account/email/login_code",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = APIClient(
            settings.PEACHJAM["CUSTOMERIO_EMAIL_API_KEY"], region=Regions.EU
        )

    def send(self, template_name, from_email, recipient_list, context, **kwargs):
        # recipient list is a list of email addresses
        if len(recipient_list) == 0 or not any(recipient_list):
            return 0

        if template_name.endswith(f".{self.template_suffix}"):
            template_name = template_name[: -len(self.template_suffix) - 1]

        if template_name not in self.transactional_templates:
            log.info(f"Sending email using Django: {template_name}")
            return super().send(
                template_name, from_email, recipient_list, context, **kwargs
            )

        self.send_with_customerio(template_name, recipient_list, context)

    def send_with_customerio(self, template_name, recipient_list, context):
        # recipient_list is a list of email addresses; the user must be pulled from the context
        user = context.pop("user", None)
        if user:
            identifiers = {"id": user.userprofile.tracking_id_str}
        else:
            identifiers = {"email": recipient_list[0]}

        # render the email
        parts = self._render_email(template_name, context)

        context["html_body"] = parts["html"]
        transactional_message_id = f"{settings.PEACHJAM['APP_NAME']}/generic"

        request = SendEmailRequest(
            transactional_message_id=transactional_message_id,
            subject=parts["subject"],
            message_data={"html_body": parts["html"]},
            identifiers=identifiers,
            attachments=context.get("attachments", {}),
            to=recipient_list,
        )
        log.info(
            f"Sending email using CustomerIO: {template_name} to {recipient_list} for {user}"
        )
        self.client.send_email(request)
