from django.conf import settings
from django.views.generic import TemplateView

from peachjam.models import CoreDocument, Locality, pj_settings


def _language_prefixes():
    """Return the URL prefixes that should be generated for robots.txt entries."""

    prefixes = [""]
    language_codes = [code for code, _ in settings.LANGUAGES]

    if len(language_codes) > 1:
        prefixes.extend(f"/{code}" for code in language_codes)

    return prefixes


def _place_codes(site_settings):
    """Return the FRBR place codes (jurisdictions and localities) used on the site."""
    jurisdiction_codes = site_settings.document_jurisdictions.all().values_list(
        "iso", flat=True
    )
    locality_codes = [
        loc.place_code()
        for loc in Locality.objects.select_related("jurisdiction").all()
    ]
    places = list(jurisdiction_codes) + list(locality_codes)
    return [place.lower() for place in places]


def _prefixed_place_rules(prefixes, places):
    """Return the disallow rules for judgment and gazette listings per language/place."""

    disallow_rules = []

    for prefix in prefixes:
        for place in places:
            base_path = f"/akn/{place}"
            disallow_rules.append(f"Disallow: {prefix}{base_path}/judgment/")
            disallow_rules.append(f"Disallow: {prefix}{base_path}/officialGazette/")

    return disallow_rules


class RobotsView(TemplateView):
    template_name = "peachjam/robots.txt"
    content_type = "text/plain"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        prefixes = _language_prefixes()

        disallowed_content = []
        for frbr_uri in (
            CoreDocument.objects.filter(allow_robots=False)
            .values_list("work_frbr_uri", flat=True)
            .order_by()
            .distinct()
        ):
            for prefix in prefixes:
                disallowed_content.append(f"Disallow: {prefix}{frbr_uri}/")

        site_settings = pj_settings()
        place_codes = _place_codes(site_settings)

        context["prefixed_disallow_paths"] = "\n".join(
            _prefixed_place_rules(prefixes, place_codes)
        )
        context["disallowed_content"] = "\n".join(disallowed_content)
        context["extra_content"] = site_settings.robots_txt or ""

        return context
