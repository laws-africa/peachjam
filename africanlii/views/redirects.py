from urllib.parse import quote

from django.shortcuts import Http404
from django.views.generic import RedirectView

from .article_redirect_urls import ARTICLE_URLS


class ArticleRedirectView(RedirectView):
    permanent = True

    def get_redirect_url(self, *args, **kwargs):
        path = quote(kwargs.get("path"))
        if path in ARTICLE_URLS:
            return "/articles/{}".format(ARTICLE_URLS[path])
        raise Http404
