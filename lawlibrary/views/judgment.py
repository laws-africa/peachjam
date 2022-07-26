from django.views.generic import ListView

from liiweb.models import CourtClass, CourtDetail
from peachjam.models import Judgment


class JudgmentListView(ListView):
    model = Judgment
    template_name = "lawlibrary/judgment_list.html"
    context_object_name = "documents"
    paginate_by = 20

    def get_context_data(self, **kwargs):
        context = super(JudgmentListView, self).get_context_data(**kwargs)

        court_classes = CourtClass.objects.values_list("name", flat=True)
        court_class_ids = list(court_classes.values_list("id", flat=True))
        courts = CourtDetail.objects.filter(court_class__in=court_class_ids)
        recent_judgments = Judgment.objects.order_by("-date")[:30]

        context["court_classes"] = court_classes
        context["courts"] = courts
        context["recent_judgments"] = recent_judgments

        return context
