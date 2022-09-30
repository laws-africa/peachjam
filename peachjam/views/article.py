from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, ListView

from peachjam.models import Article, UserProfile


class ArticleListView(ListView):
    model = Article
    queryset = Article.objects.filter(published=True).order_by("-date")
    template_name = "peachjam/article_list.html"
    context_object_name = "articles"
    navbar_link = "articles"
    paginate_by = 5


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
        return context


class UserProfileDetailView(DetailView):
    model = UserProfile
    template_name = "peachjam/user_profile.html"
    context_object_name = "user_profile"

    def get_object(self):
        return get_object_or_404(UserProfile, user__username=self.kwargs["username"])
