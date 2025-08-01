import re
from urllib.parse import urlparse

import lxml.html
from cobalt.uri import FrbrUri
from corsheaders.signals import check_request_enabled
from django.conf import settings
from django.http import Http404
from django.shortcuts import redirect
from django.utils.translation import get_language
from django.views.generic import DetailView

from peachjam.helpers import add_slash
from peachjam.models import CoreDocument
from peachjam.resolver import RedirectResolver, resolver


class DocumentPopupView(DetailView):
    """Shows a popup with basic details for a document.

    An affiliate site may use this by redirecting a local popup to a popup on (this) LII website.
    So we allow CORS requests, provided the origin matches the partner website.

    For example:

    1. The user hovers over a link to /akn/xx/act/2009/1 on africanlii.org
    2. The browser asks africanlii.org for the popup, but it doesn't exist on africanlii.org
    3. So africanlii.org uses peachjam's resolver logic to identify that xxlii.org is responsible for /akn/xx/...
       and redirects the user's browser to xxlii.org/p/africanlii.org/e/popup/akn/xx/act/2009/1
    4. This view loads on xxlii.org and shows the popup, because the request came from africanlii.org
       which matches the partner code in the URL
    """

    model = CoreDocument
    context_object_name = "document"
    template_name = "peachjam/document_popup.html"
    partner_domains = [x["domain"] for x in RedirectResolver.RESOLVER_MAPPINGS.values()]
    localhost = ["localhost", "127.0.0.1"]
    frbr_uri = None

    def get(self, request, partner, frbr_uri, *args, **kwargs):
        # check partner matches requesting host
        if not self.valid_partner(request, partner):
            raise Http404()

        try:
            self.object = self.get_object()
        except Http404:
            if self.frbr_uri:
                # use the resolver to send a redirect if it's probably off-site somewhere
                domain = resolver.get_domain_for_frbr_uri(self.frbr_uri)
                if domain:
                    return redirect(f"https://{domain}{self.request.path}")
            raise

        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)

    def valid_partner(self, request, partner):
        # only allow this page to be embedded from valid partners
        # first, the partner must match the referer (or origin, for CORS requests)
        referrer = request.META.get("HTTP_REFERER") or request.META.get("HTTP_ORIGIN")
        if referrer and not settings.DEBUG:
            try:
                parsed = urlparse(referrer)
                if parsed.hostname != partner and parsed.hostname not in self.localhost:
                    return False
            except ValueError:
                return False
        # second, the partner must be in the list of valid partners
        return partner in self.partner_domains or partner in self.localhost

    def get_object(self, *args, **kwargs):
        try:
            self.frbr_uri = FrbrUri.parse(add_slash(self.kwargs["frbr_uri"]))
        except ValueError:
            raise Http404()

        self.portion = self.frbr_uri.portion
        self.frbr_uri.portion = None
        if self.frbr_uri.expression_date:
            uri = self.frbr_uri.expression_uri()
        else:
            uri = self.frbr_uri.work_uri()

        obj = self.model.objects.prefetch_related("labels").best_for_frbr_uri(
            uri, get_language()
        )[0]
        if not obj:
            raise Http404()
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.portion:
            if not (self.object.content_html and self.object.content_html_is_akn):
                raise Http404()

            # try to find the portion within the object
            try:
                elems = self.object.content_html_tree.xpath(
                    f'//*[@id="{self.portion}"]'
                )
                if elems:
                    context["portion_html"] = lxml.html.tostring(
                        elems[0], encoding="unicode"
                    )
            except ValueError:
                raise Http404()

        # is this a CORS request from off-site? (the partner host is not the same as the local host)
        context["offsite_request"] = self.request.get_host() != self.kwargs["partner"]

        return context


url_re = re.compile("^/p/([^/]+)/e/.*")


def check_cors_and_partner(sender, request, **kwargs):
    """Check if we should mark this request as CORS-enabled. We do so if it's popup URL and
    the origin matches the partner domain."""
    match = url_re.match(request.path_info)
    if match:
        # allow a CORS request if the partner portion of the URL matches the origin
        origin = request.META.get("HTTP_ORIGIN")
        if origin:
            try:
                return urlparse(origin).hostname == match.group(1)
            except ValueError:
                return False


check_request_enabled.connect(check_cors_and_partner)
