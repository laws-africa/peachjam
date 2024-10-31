from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import DetailView, ListView

from peachjam.models import Article, Taxonomy, UserProfile
from peachjam.views.generic_views import YearMixin


class ArticleViewMixin:
    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context["article_tags"] = sorted(
            Article.get_article_tags_root().get_descendants(), key=lambda x: x.name
        )
        context["recent_articles"] = Article.objects.filter(published=True).order_by(
            "-date"
        )[:8]
        return context


class ArticleListView(ArticleViewMixin, ListView):
    model = Article
    queryset = (
        Article.objects.filter(published=True)
        .select_related("author")
        .prefetch_related("topics")
        .order_by("-date")
    )
    template_name = "peachjam/article_list.html"
    context_object_name = "articles"
    navbar_link = "articles"
    paginate_by = 20

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        self.populate_years(context)
        return context

    def populate_years(self, context):
        years = (
            self.queryset.dates("date", "year", order="DESC")
            .values_list("date__year", flat=True)
            .distinct()
        )
        context["years"] = [
            {"url": reverse("article_year_archive", args=[y]), "year": y} for y in years
        ]
        context["all_years_url"] = reverse("article_list")


class ArticleYearView(YearMixin, ArticleListView):
    def get_queryset(self):
        return super().get_queryset().filter(date__year=self.year)


class ArticleTopicView(ArticleListView):
    template_name = "peachjam/article_topic_detail.html"

    def get(self, *args, **kwargs):
        self.topic = get_object_or_404(Taxonomy.objects.filter(slug=kwargs["topic"]))
        return super().get(*args, **kwargs)

    def get_queryset(self):
        return super().get_queryset().filter(topics=self.topic)

    def get_context_data(self, **kwargs):
        return super().get_context_data(topic=self.topic, **kwargs)

    def populate_years(self, context):
        years = (
            self.queryset.filter(topics=self.topic)
            .dates("date", "year", order="DESC")
            .values_list("date__year", flat=True)
            .distinct()
        )
        context["years"] = [
            {"url": reverse("article_topic_year", args=[self.topic.slug, y]), "year": y}
            for y in years
        ]
        context["all_years_url"] = reverse("article_topic", args=[self.topic.slug])


class ArticleTopicYearView(YearMixin, ArticleTopicView):
    def get_queryset(self):
        return super().get_queryset().filter(date__year=self.kwargs["year"])


class ArticleDetailView(ArticleViewMixin, DetailView):
    model = Article
    queryset = Article.objects.filter(published=True)
    template_name = "peachjam/article_detail.html"
    context_object_name = "article"

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(
            date=self.kwargs["date"], author__username=self.kwargs["author"]
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["user_profile"] = get_object_or_404(
            UserProfile, user__pk=self.object.author.pk
        )
        return context


class ArticleAuthorDetailView(ArticleListView):
    template_name = "peachjam/article_author.html"

    def dispatch(self, *args, **kwargs):
        self.user_profile = get_object_or_404(
            UserProfile, user__username=kwargs["username"]
        )
        return super().dispatch(*args, **kwargs)

    def get_queryset(self):
        return super().get_queryset().filter(author=self.user_profile.user)

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs, user_profile=self.user_profile)

    def populate_years(self, context):
        years = (
            self.queryset.filter(author=self.user_profile.user)
            .dates("date", "year", order="DESC")
            .values_list("date__year", flat=True)
            .distinct()
        )
        context["years"] = [
            {
                "url": reverse(
                    "article_author_year", args=[self.user_profile.user.username, y]
                ),
                "year": y,
            }
            for y in years
        ]
        context["all_years_url"] = reverse(
            "article_author", args=[self.user_profile.user.username]
        )


class ArticleAuthorYearDetailView(YearMixin, ArticleAuthorDetailView):
    def get_queryset(self):
        return super().get_queryset().filter(date__year=self.kwargs["year"])
