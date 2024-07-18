from django.utils.translation import get_language_from_request

from africanlii.constants import LIIS
from africanlii.models import (
    AfricanUnionInstitution,
    AfricanUnionOrgan,
    MemberState,
    RegionalEconomicCommunity,
)
from peachjam.models import Article, CoreDocument, CourtClass, GenericDocument, Taxonomy
from peachjam.views import HomePageView as BaseHomePageView


class HomePageView(BaseHomePageView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        recent_articles = (
            Article.objects.prefetch_related("topics")
            .filter(published=True)
            .select_related("author")
            .order_by("-date")[:5]
        )

        context["recent_articles"] = recent_articles
        context["recent_soft_law"] = (
            GenericDocument.objects.exclude(published=False)
            .exclude(frbr_uri_doctype="doc")
            .prefetch_related("labels")
            .order_by("-date")[:5]
        )
        context["recent_reports_guides"] = (
            GenericDocument.objects.exclude(published=False)
            .filter(frbr_uri_doctype="doc")
            .prefetch_related("labels")
            .order_by("-date")[:5]
        )
        context["recent_legal_instruments"] = (
            CoreDocument.objects.exclude(published=False)
            .filter(frbr_uri_doctype="act")
            .prefetch_related("labels")
            .order_by("-date")[:5]
        )
        context["au_organs"] = AfricanUnionOrgan.objects.prefetch_related("author")
        context["au_institutions"] = AfricanUnionInstitution.objects.prefetch_related(
            "author"
        )
        context["recs"] = RegionalEconomicCommunity.objects.prefetch_related("locality")
        context["member_states"] = MemberState.objects.prefetch_related("country")
        context["taxonomies"] = Taxonomy.dump_bulk()
        context["taxonomy_url"] = "taxonomy_detail"
        context["court_classes"] = CourtClass.objects.prefetch_related("courts")

        context["liis"] = LIIS

        # check user's preferred language
        current_language = get_language_from_request(self.request)
        video_links = {
            "en": "https://www.youtube.com/embed/m54qqXDkCfk",
            "fr": "https://www.youtube.com/embed/BMN38Hvt6Uw",
            "sw": "https://www.youtube.com/embed/CbtPXhdTZyA",
        }

        # set video link based on user's preferred language, default to English if not available
        context["video_link"] = video_links.get(current_language, video_links["en"])

        return context
