from django.views.generic import ListView

from peachjam.models import Article


class ArticleListView(ListView):
    model = Article
    template_name = "lawlibrary/article_list.html"
