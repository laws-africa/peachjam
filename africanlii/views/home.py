from africanlii.models import (
    AfricanUnionInstitution,
    AfricanUnionOrgan,
    MemberState,
    RegionalEconomicCommunity,
)
from peachjam.models import Article, CoreDocument, GenericDocument, Taxonomy
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
        context["taxonomies"] = Taxonomy.get_tree()
        context["liis"] = [
            {
                "name": "GhaLII",
                "country": "Ghana",
                "url": "https://ghalii.org",
                "logo": "images/liis/ghalii.png",
            },
            {
                "name": "Kenya Law",
                "country": "Kenya",
                "url": "http://kenyalaw.org",
                "logo": "images/liis/kenyalaw.png",
            },
            {
                "name": "LesothoLII",
                "country": "Lesotho",
                "url": "https://lesotholii.org",
                "logo": "images/liis/lesotholii.png",
            },
            {
                "name": "MalawiLII",
                "country": "Malawi",
                "url": "https://malawilii.org",
                "logo": "images/liis/malawilii.png",
            },
            {
                "name": "NamibLII",
                "country": "Namibia",
                "url": "https://namiblii.org",
                "logo": "images/liis/namiblii.png",
            },
            {
                "name": "SierraLII",
                "country": "Sierra Leone",
                "url": "https://sierralii.org",
                "logo": "images/liis/sierralii.png",
            },
            {
                "name": "SeyLII",
                "country": "Seychelles",
                "url": "https://seylii.org",
                "logo": "images/liis/seylii.png",
            },
            {
                "name": "LawLibrary",
                "country": "South Africa",
                "url": "https://lawlibrary.org.za",
                "logo": "images/liis/lawlibrary.png",
            },
            {
                "name": "TanzLII",
                "country": "Tanzania",
                "url": "https://tanzlii.org",
                "logo": "images/liis/tanzlii.png",
            },
            {
                "name": "ULII",
                "country": "Uganda",
                "url": "https://ulii.org",
                "logo": "images/liis/ulii.png",
            },
            {
                "name": "ZambiaLII",
                "country": "Zambia",
                "url": "https://zambialii.org",
                "logo": "images/liis/zambialii.png",
            },
            {
                "name": "ZanzibarLII",
                "country": "Zanzibar",
                "url": "https://zanzibarlii.org",
                "logo": "images/liis/zanzibarlii.png",
            },
            {
                "name": "ZimLII",
                "country": "Zimbabwe",
                "url": "https://zimlii.org",
                "logo": "images/liis/zimlii.png",
            },
        ]
        for lii in context["liis"]:
            lii["domain"] = lii["url"].split("/", 3)[2]

        return context
