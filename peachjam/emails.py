from django.conf import settings
from django.contrib.sites.models import Site
from templated_email.backends.vanilla_django import (
    TemplateBackend as BaseTemplateBackend,
)


class TemplateBackend(BaseTemplateBackend):
    def _render_email(
        self, template_name, context, template_dir=None, file_extension=None
    ):
        if not context.get("user"):
            raise Exception("Context must contain a user")

        # inject common context
        context["site"] = Site.objects.get_current()
        context["APP_NAME"] = settings.PEACHJAM["APP_NAME"]

        return super()._render_email(
            template_name,
            context,
            template_dir=template_dir,
            file_extension=file_extension,
        )
