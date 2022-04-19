from django.views.generic import DetailView, ListView, TemplateView

from africanlii.models import Judgment
from peachjam.views import AuthedViewMixin


class JudgmentListView(AuthedViewMixin, ListView):
    model = Judgment
    template_name = "africanlii/judgment_list.html"
    context_object_name = "documents"
    paginate_by = 20


class JudgmentDetailView(AuthedViewMixin, DetailView):
    model = Judgment
    template_name = "africanlii/judgment_detail.html"
    context_object_name = "judgment"


class HomePageView(AuthedViewMixin, TemplateView):
    template_name = "africanlii/home.html"
