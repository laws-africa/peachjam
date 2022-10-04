from django.views.generic import TemplateView

from peachjam.models import CourtClass, Judgment


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
                    {"title": court.name, "code": court.code}
                    for court in court_class.courts.order_by("name")
                ],
            }

            grouped_courts.append(court_dict)

        context["grouped_courts"] = grouped_courts
        context["recent_judgments"] = Judgment.objects.order_by("-date")[:30]
        return context
