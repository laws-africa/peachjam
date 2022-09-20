from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, ListView

from peachjam.models import Article, UserProfile


class ArticleListView(ListView):
    model = Article
    template_name = "peachjam/article_list.html"
    context_object_name = "articles"


class ArticleDetailView(DetailView):
    model = Article
    template_name = "peachjam/article_detail.html"
    context_object_name = "article"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["user_profile"] = get_object_or_404(
            UserProfile, pk=self.object.author.pk
        )
        return context


class UserProfileDetailView(DetailView):
    model = UserProfile
    template_name = "peachjam/user_profile.html"
    context_object_name = "user_profile"
