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

        courts = []
        for court_class in CourtClass.objects.all():
            court_dict = {
                "court_class": court_class.name,
                "courts": CourtDetail.objects.filter(court_class=court_class),
            }
            courts.append(court_dict)

        recent_judgments = Judgment.objects.order_by("-date")[:30]

        context["courts"] = courts
        context["recent_judgments"] = recent_judgments

        return context
