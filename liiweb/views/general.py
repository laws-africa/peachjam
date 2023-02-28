from django.views.generic import TemplateView

from peachjam.models import CourtClass, Judgment, Legislation, Taxonomy


class HomePageView(TemplateView):
    template_name = "liiweb/home.html"

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
        context["recent_judgments"] = Judgment.objects.order_by("-date")[:5]
        context["recent_legislation"] = Legislation.objects.filter(
            metadata_json__stub=False
        ).order_by("-date")[:10]
        context["taxonomies"] = Taxonomy.get_tree()
        return context


class PocketlawView(TemplateView):
    template_name = "liiweb/pocketlaw.html"

    def get_context_data(self, **kwargs):
        return super().get_context_data(pocketlaw_version="1.0.7", **kwargs)
