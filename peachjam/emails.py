import logging

from customerio import APIClient, Regions, SendEmailRequest
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.db.models import QuerySet
from templated_email.backends.vanilla_django import (
    TemplateBackend as BaseTemplateBackend,
)

from peachjam.models import CoreDocument

log = logging.getLogger(__name__)


class TemplateBackend(BaseTemplateBackend):
    def supplement_context(self, context):
        if not context.get("user"):
            raise Exception("Context must contain a user")

        # inject common context
        context["site"] = Site.objects.get_current()
        context["APP_NAME"] = settings.PEACHJAM["APP_NAME"]

    def _render_email(
        self, template_name, context, template_dir=None, file_extension=None
    ):
        self.supplement_context(context)
        return super()._render_email(
            template_name,
            context,
            template_dir=template_dir,
            file_extension=file_extension,
        )


class CustomerIOTemplateBackend(TemplateBackend):
    """Sends emails using CustomerIO.

    This requires us to serialise the context to JSON and send it to CustomerIO, and to add additional context
    such as site information.

    When serialising, if a key called xxx_url_path is found, a new key called xxx_url is added which is the site's URL
    plus the path.
    """

    serializers = {
        User: lambda context, user: {
            "email": user.email,
            "tracking_id": user.userprofile.tracking_id_str,
        },
        CoreDocument: lambda context, doc: {
            "title": doc.title,
            "url_path": doc.get_absolute_url(),
        },
    }

    # use CustomerIO for these templates, otherwise fall back to the usual system
    transactional_message_ids = ["user_following_alert"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = APIClient(
            settings.PEACHJAM["CUSTOMERIO_EMAIL_API_KEY"], region=Regions.EU
        )

    def send(self, template_name, from_email, recipient_list, context, **kwargs):
        if template_name.endswith(f".{self.template_suffix}"):
            template_name = template_name[: -len(self.template_suffix) - 1]

        if template_name not in self.transactional_message_ids:
            log.info(f"Sending email using Django: {template_name}")
            return super().send(
                template_name, from_email, recipient_list, context, **kwargs
            )

        transactional_message_id = f"{settings.PEACHJAM['APP_NAME']}/{template_name}"
        self.supplement_context(context)

        request = SendEmailRequest(
            transactional_message_id=transactional_message_id,
            message_data=context,
            identifiers={"id": context["user"]["tracking_id"]},
            to=context["user"]["email"],
        )
        log.info(
            f"Sending email using CustomerIO: {transactional_message_id} to {context['user']}"
        )
        self.client.send_email(request)

    def supplement_context(self, context):
        super().supplement_context(context)

        # inject this first so the other serializers can use the site details
        context["site"] = {
            "name": context["APP_NAME"],
            "domain": context["site"].domain,
            "url": f'https://{context["site"].domain}',
        }

        for key, value in context.items():
            context[key] = self.serialize(context, value)

        self.rewrite_url_paths(context)

    def serialize(self, context, obj):
        if isinstance(obj, (list, QuerySet)):
            return [self.serialize(context, item) for item in obj]

        if isinstance(obj, dict):
            return {key: self.serialize(context, value) for key, value in obj.items()}

        # walk up the object's class hierarchy to find the first serializer
        for cls in obj.__class__.mro():
            if cls in self.serializers:
                # custom serializer
                return self.serializers[cls](context, obj)

        return str(obj)

    def rewrite_url_paths(self, context):
        """Recursively prepend the site's URL to any [xxx_]url_path keys in the context."""

        def rewrite(info):
            for key, value in list(info.items()):
                if isinstance(value, dict):
                    rewrite(value)

                if isinstance(value, list):
                    for x in value:
                        if isinstance(x, dict):
                            rewrite(x)

                elif isinstance(value, str) and key.endswith("url_path"):
                    # add a new member xxx_url which is the site's URL plus the path
                    info[key[:-8] + "url"] = f'{context["site"]["url"]}{value}'

        rewrite(context)
