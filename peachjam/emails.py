import logging

import css_inline
from customerio import APIClient, Regions, SendEmailRequest
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.contrib.staticfiles import finders
from django.db.models import QuerySet
from templated_email.backends.vanilla_django import (
    TemplateBackend as BaseTemplateBackend,
)

from peachjam.models import CoreDocument, ProvisionCitation
from peachjam_search.models import SavedSearch
from peachjam_search.serializers import SearchHit

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


def document_serializer(context, doc):
    return {
        "title": doc.title,
        "url_path": doc.get_absolute_url(),
        "blurb": getattr(doc, "blurb", None),
        "flynote": getattr(doc, "flynote", None),
    }


def search_hit_serializer(context, hit):
    d = hit.as_dict()
    d["document"] = document_serializer(context, hit.document) if hit.document else None
    return d


class CustomerIOTemplateBackend(TemplateBackend):
    """Sends emails using CustomerIO if enabled, falling back to the usual Django email system otherwise.

    This requires us to serialise the context to JSON and send it to CustomerIO, and to add additional context
    such as site information.

    When serialising, if a key called xxx_url_path is found, a new key called xxx_url is added which is the site's URL
    plus the path.
    """

    serializers = {
        CoreDocument: document_serializer,
        SearchHit: search_hit_serializer,
        SavedSearch: lambda context, obj: {
            "q": obj.q,
            "name": str(obj),
            "url_path": obj.get_absolute_url(),
        },
        User: lambda context, user: {
            "email": user.email,
            "tracking_id": user.userprofile.tracking_id_str,
        },
        ProvisionCitation: lambda context, pc: {
            "document": document_serializer(context, pc.citing_document),
            "prefix": pc.prefix,
            "suffix": pc.suffix,
            "exact": pc.exact,
            "provision_eid": pc.provision_eid,
        },
    }

    # use CustomerIO for these templates, otherwise fall back to the usual system
    transactional_message_ids = [
        "search_alert",
        "user_following_alert",
        "new_citation_alert",
    ]

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
            # tell supplement_context not to serialise the context
            context["USE_SERIALISERS"] = False
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

        if context.get("USE_SERIALISERS") is False:
            return

        if not context.get("user"):
            raise Exception("Context must contain a user")

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
