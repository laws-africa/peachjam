from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from peachjam.models import Article, Legislation


class StaticPageSitemap(Sitemap):
    """Public, site-configured pages that are appropriate search landing pages."""

    priority = 0.8

    def items(self):
        return settings.PEACHJAM.get("SITEMAP_STATIC_URL_NAMES", [])

    def location(self, item):
        return reverse(item)


class ArticleSitemap(Sitemap):
    priority = 0.7
    changefreq = "monthly"

    def items(self):
        return Article.objects.filter(published=True).select_related("author")

    def lastmod(self, item):
        return item.date


class LegislationSitemap(Sitemap):
    """The current, public expression of each legislation work."""

    priority = 0.9
    changefreq = "weekly"

    def items(self):
        return (
            Legislation.objects.filter(
                allow_robots=True,
                published=True,
                restricted=False,
            )
            .latest_expression()
            .select_related("work")
        )

    def lastmod(self, item):
        return item.updated_at


sitemaps = {
    "pages": StaticPageSitemap,
    "articles": ArticleSitemap,
    "legislation": LegislationSitemap,
}
