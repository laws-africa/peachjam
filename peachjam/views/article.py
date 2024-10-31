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
        )[:5]
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
        years = (
            self.model.objects.filter(published=True)
            .dates("date", "year", order="DESC")
            .values_list("date__year", flat=True)
            .distinct()
        )

        context["years"] = [
            {"url": reverse("article_year_archive", args=[y]), "year": y} for y in years
        ]

        context["all_years_url"] = reverse("article_list")

        return context


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


class ArticleTopicYearView(YearMixin, ArticleTopicView):
    def get_queryset(self):
        return super().get_queryset().filter(date__year=self.kwargs["year"])

    def get_context_data(self, **kwargs):
        return super().get_context_data(year=self.kwargs["year"])


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


class UserProfileDetailView(DetailView):
    model = UserProfile
    template_name = "peachjam/user_profile.html"
    context_object_name = "user_profile"

    def get_object(self, queryset=None):
        return get_object_or_404(UserProfile, user__username=self.kwargs["username"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["articles"] = (
            context["object"].user.articles.filter(published=True).order_by("-date")
        )
        return context
