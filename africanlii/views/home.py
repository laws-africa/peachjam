from africanlii.models import (
    AfricanUnionInstitution,
    AfricanUnionOrgan,
    MemberState,
    RegionalEconomicCommunity,
)
from peachjam.models import Article, CoreDocument, GenericDocument
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
        context["recent_soft_law"] = GenericDocument.objects.exclude(
            frbr_uri_doctype="doc"
        ).order_by("-date")[:5]
        context["recent_reports_guides"] = GenericDocument.objects.filter(
            frbr_uri_doctype="doc"
        ).order_by("-date")[:5]
        context["recent_legal_instruments"] = CoreDocument.objects.filter(
            frbr_uri_doctype="act"
        ).order_by("-date")[:5]
        context["au_organs"] = AfricanUnionOrgan.objects.prefetch_related("author")
        context["au_institutions"] = AfricanUnionInstitution.objects.prefetch_related(
            "author"
        )
        context["recs"] = RegionalEconomicCommunity.objects.prefetch_related("locality")
        context["member_states"] = MemberState.objects.prefetch_related("country")
        context["liis"] = [
            {
                "name": "GhalII",
                "country": "Ghana",
                "url": "https://ghalii.org",
                "logo": "https://ghalii.org/static/images/logo.png",
            },
            {
                "name": "Kenya Law",
                "country": "Kenya",
                "url": "http://kenyalaw.org",
                "logo": "",
            },
            {
                "name": "LesothoLII",
                "country": "Lesotho",
                "url": "https://lesotholii.org",
                "logo": "https://lesotholii.org/static/images/logo.png",
            },
            {
                "name": "MalawiLII",
                "country": "Malawi",
                "url": "https://malawilii.org",
                "logo": "https://malawilii.org/static/images/logo.png",
            },
            {
                "name": "Namiblii",
                "country": "Namibia",
                "url": "https://namiblii.org",
                "logo": "https://namiblii.org/static/images/logo.png",
            },
            {
                "name": "SierraLII",
                "country": "Sierra Leone",
                "url": "https://sierralii.org",
                "logo": "https://sierralii.org/static/images/logo.png",
            },
            {
                "name": "SeyLII",
                "country": "Seychelles",
                "url": "https://seylii.org",
                "logo": "https://seylii.org/static/images/logo.png",
            },
            {
                "name": "LawLibrary",
                "country": "South Africa",
                "url": "https://lawlibrary.org.za",
                "logo": "https://lawlibrary.org.za/static/images/lawlibrary-logo.png",
            },
            {
                "name": "TanzLII",
                "country": "Tanzania",
                "url": "https://tanzlii.org",
                "logo": "https://tanzlii.org/static/images/logo.png",
            },
            {
                "name": "ULII",
                "country": "Uganda",
                "url": "https://ulii.org",
                "logo": "https://ulii.org/static/images/logo.png",
            },
            {
                "name": "ZambiaLII",
                "country": "Zambia",
                "url": "https://zambialii.org",
                "logo": "https://zambialii.org/static/images/logo.png",
            },
            {
                "name": "ZanzibarLII",
                "country": "Zanzibar",
                "url": "https://zanzibarlii.org",
                "logo": "https://zanzibarlii.org/static/images/logo.png",
            },
            {
                "name": "ZimLII",
                "country": "Zimbabwe",
                "url": "https://zimlii.org",
                "logo": "https://zimlii.org/static/images/logo.png",
            },
        ]

        return context
