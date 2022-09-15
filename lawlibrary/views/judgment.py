from django.views.generic import TemplateView

from liiweb.models.court import CourtClass
from peachjam.models import Judgment


class JudgmentListView(TemplateView):
    model = Judgment
    template_name = "lawlibrary/judgment_list.html"
    navbar_link = "judgments"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        grouped_courts = []
        for court_class in CourtClass.objects.all():
            court_dict = {
                "title": court_class.name,
                "items": [
                    {"title": court_detail.court.name, "code": court_detail.court.code}
                    for court_detail in court_class.courtdetail_set.all()
                ],
            }

            grouped_courts.append(court_dict)

        context["grouped_courts"] = grouped_courts
        context["recent_judgments"] = Judgment.objects.order_by("-date")[:30]
        return context
