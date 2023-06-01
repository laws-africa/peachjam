from itertools import groupby
from operator import itemgetter

from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import DetailView, ListView
from django.views.generic.dates import MonthArchiveView, YearArchiveView

from peachjam.models import Article, Taxonomy, UserProfile


def group_years(years):
    # sort list of years
    years.sort(key=lambda x: x["year"], reverse=True)

    results = []
    # group list of years dict by year
    for key, value in groupby(years, key=itemgetter("year")):
        year_dict = {
            "year": key,
            "url": reverse("article_year_archive", kwargs={"year": key}),
        }
        results.append(year_dict)
    print(results)
    return results


class ArticleListView(ListView):
    model = Article
    queryset = Article.objects.filter(published=True).order_by("-date")
    template_name = "peachjam/article_list.html"
    context_object_name = "articles"
    navbar_link = "articles"
    paginate_by = 10

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        years = sorted(
            list(
                self.model.objects.filter(published=True)
                .order_by()
                .values_list("date__year", flat=True)
                .distinct()
            ),
            reverse=True,
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
            .exclude(pk=self.object.pk)
            .order_by("-date")[:5]
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


class ArticleYearArchiveView(YearArchiveView):
    model = Article
    date_field = "date"
    make_object_list = True
    allow_future = True
    context_object_name = "articles"
    paginate_by = 10
    template_name = "peachjam/article_list.html"

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(**kwargs)
        years = sorted(
            list(
                self.model.objects.filter(published=True)
                .order_by()
                .values_list("date__year", flat=True)
                .distinct()
            ),
            reverse=True,
        )

        context["years"] = [
            {"url": reverse("article_year_archive", args=[y]), "year": y} for y in years
        ]

        context["all_years_url"] = reverse("article_list")

        return context


class ArticleMonthArchiveView(MonthArchiveView):
    model = Article
    date_field = "date"
    allow_future = True
