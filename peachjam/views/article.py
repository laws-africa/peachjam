from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.dates import MONTHS
from django.views.generic import DetailView, ListView
from django.views.generic.dates import YearArchiveView

from peachjam.models import Article, ArticleAttachment, Taxonomy, UserProfile


class ArticleListView(ListView):
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
    paginate_by = 10

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


class ArticleTopicListView(ArticleListView):
    template_name = "peachjam/article_topic_list.html"

    def get(self, *args, **kwargs):
        self.topic = get_object_or_404(Taxonomy.objects.filter(slug=kwargs["topic"]))
        return super().get(*args, **kwargs)

    def get_queryset(self):
        return super().get_queryset().filter(topics=self.topic)

    def get_context_data(self, **kwargs):
        return super().get_context_data(topic=self.topic, **kwargs)


class ArticleDetailView(DetailView):
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
        context["more_articles"] = (
            Article.objects.filter(author=self.object.author, published=True)
            .select_related("author")
            .prefetch_related("topics")
            .exclude(pk=self.object.pk)
            .order_by("-date")[:5]
        )
        return context


class ArticleAttachmentDetailView(DetailView):
    model = ArticleAttachment

    def get_object(self, queryset=None):
        return get_object_or_404(
            ArticleAttachment,
            document__date=self.kwargs["date"],
            document__slug=self.kwargs["slug"],
            document__author__username=self.kwargs["author"],
            pk=self.kwargs["pk"],
            filename=self.kwargs["filename"],
        )

    def render_to_response(self, context, **response_kwargs):
        return FileResponse(self.object.file, filename=self.object.filename)


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


class ArticleYearArchiveView(YearArchiveView):
    queryset = (
        Article.objects.select_related("author")
        .prefetch_related("topics")
        .filter(published=True)
        .order_by("-date")
    )
    date_field = "date"
    make_object_list = True
    allow_future = True
    context_object_name = "articles"
    paginate_by = 10
    template_name = "peachjam/article_list.html"
    navbar_link = "articles"

    def get_queryset(self):
        qs = self.queryset
        if self.get_year() is not None:
            qs = qs.filter(date__year=self.get_year())
        return qs

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(**kwargs)
        years = (
            self.queryset.order_by("-date__year")
            .dates("date", "year", order="DESC")
            .values_list("date__year", flat=True)
            .distinct()
        )

        context["years"] = [
            {"url": reverse("article_year_archive", args=[y]), "year": y} for y in years
        ]

        context["all_years_url"] = reverse("article_list")
        context["year"] = int(self.kwargs["year"])
        context["grouped_articles"] = self.grouped_articles(self.get_queryset())

        return context

    def grouped_articles(self, queryset):
        """Group the articles by month and return a list of dicts with the month name and articles for that month"""

        # Get the distinct months from the queryset
        months = queryset.dates(self.date_field, "month")

        # Create a list of { month: month_name, articles: [list of articles] } dicts
        grouped_articles = [
            {"month": MONTHS[m.month], "articles": queryset.filter(date__month=m.month)}
            for m in months
        ]

        return grouped_articles
