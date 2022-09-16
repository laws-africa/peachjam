from django.views.generic import DetailView, ListView

from peachjam.models import Article


class ArticleListView(ListView):
    model = Article
    template_name = "lawlibrary/article_list.html"


class ArticleDetailView(DetailView):
    model = Article
    template_name = "lawlibrary/article_detail.html"
