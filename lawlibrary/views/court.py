from django.shortcuts import get_object_or_404
from django.views.generic import DetailView

from peachjam.models import Author, Judgment


class CourtDetailView(DetailView):
    model = Author
    template_name = "lawlibrary/court_detail.html"

    def get_context_data(self, **kwargs):
        court = get_object_or_404(Author, pk=self.kwargs["pk"])
        context = super().get_context_data(**kwargs)

        judgments = Judgment.objects.filter(author=court)

        context["court"] = court
        context["judgments"] = judgments

        return context
