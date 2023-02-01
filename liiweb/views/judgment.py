from django.views.generic import TemplateView

from peachjam.models import CourtClass, Judgment


class JudgmentListView(TemplateView):
    model = Judgment
    template_name = "liiweb/../../peachjam/templates/peachjam/judgment_list.html"
    navbar_link = "judgments"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        court_classes = (
            CourtClass.objects.select_related("courts")
            .order_by("name", "courts__name")
            .values("name", "courts__name", "courts__code")
            .all()
        )
        grouped_courts = {}
        for c_c in court_classes:
            grouped_courts.setdefault(c_c["name"], [])
            if c_c.get("courts__name") and c_c.get("courts__code"):
                grouped_courts[c_c["name"]].append(
                    {"title": c_c["courts__name"], "code": c_c["courts__code"]}
                )

        context["grouped_courts"] = grouped_courts
        context["recent_judgments"] = Judgment.objects.order_by("-date")[:30]
        return context
