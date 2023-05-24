from django.shortcuts import Http404
from django.views.generic import RedirectView

ARTICLE_URLS = {
    "20230505/there-room-general-unjustified-enrichment-action-south-african-law": "2023-05-05/fasken/there-is-room-for-a-general-unjustified-enrichment-action-in-south-african-law",  # noqa: E501
}


class ArticleRedirectView(RedirectView):
    permanent = True

    def get_redirect_url(self, *args, **kwargs):
        path = kwargs.get("path")
        if path in ARTICLE_URLS:
            return "/articles/{}".format(ARTICLE_URLS[path])
        raise Http404
