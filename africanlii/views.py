from django.views.generic import DetailView
from django.views.generic import ListView
from django.views.generic import TemplateView

from africanlii.models import Judgment
from peachjam.views import AuthedViewMixin


class JudgmentListView(AuthedViewMixin, ListView):
    template_name = "africanlii/judgment_list.html"
    context_object_name = "judgments"

    def get_queryset(self):
        return Judgment.objects.all()


class JudgmentDetailView(AuthedViewMixin, DetailView):
    model = Judgment
    template_name = "africanlii/judgment_detail.html"
    context_object_name = "judgment"


class HomePageView(AuthedViewMixin, TemplateView):
    template_name = "africanlii/home.html"
