from itertools import groupby

from django.views.generic import ListView

from peachjam.models import Legislation, Locality
from peachjam.registry import registry
from peachjam.views import BaseDocumentDetailView
from peachjam_api.serializers import LegislationSerializer


class LegislationListView(ListView):
    model = Legislation
    template_name = "lawlibrary/legislation_list.html"
    context_object_name = "documents"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        qs = (
            self.get_queryset()
            .filter(locality=None)
            .distinct("work_frbr_uri")
            .order_by("work_frbr_uri", "-date")
        )
        context["national_legislation_list"] = LegislationSerializer(qs, many=True).data

        provincial_legislation_list = []

        for jurisdiction in self.get_jurisdictions():
            locality_dict = {
                "localities": [
                    {
                        "code": locality.code,
                        "name": locality.name,
                    }
                    for locality in Locality.objects.filter(
                        jurisdiction__name=jurisdiction
                    )
                ],
            }
            provincial_legislation_list.append(locality_dict)

        context["provincial_legislation_list"] = provincial_legislation_list
        return context

    def get_years(self):
        qs = (
            self.get_queryset()
            .filter(locality=None)
            .order_by()
            .values_list("date__year", flat=True)
            .distinct()
        )
        return sorted(qs, reverse=True)

    def get_jurisdictions(self):
        return (
            self.get_queryset()
            .order_by("jurisdiction__name")
            .values_list("jurisdiction__name", flat=True)
            .distinct()
        )


class ProvincialLegislationListView(ListView):
    model = Legislation
    template_name = "lawlibrary/provincial_legislation_list.html"
    context_object_name = "documents"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        qs = (
            self.get_queryset()
            .filter(locality__code=self.kwargs["code"])
            .distinct("work_frbr_uri")
            .order_by("work_frbr_uri", "-date")
        )

        context["legislation_table"] = LegislationSerializer(qs, many=True).data
        context["facet_data"] = {"years": self.get_years()}

        return context

    def get_years(self):
        qs = (
            self.get_queryset()
            .filter(locality__code=self.kwargs["code"])
            .order_by()
            .values_list("date__year", flat=True)
            .distinct()
        )
        return sorted(qs, reverse=True)


@registry.register_doc_type("legislation")
class LegislationDetailView(BaseDocumentDetailView):
    model = Legislation
    template_name = "lawlibrary/legislation_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        timeline_events = self.get_timeline_events()
        context["timeline_events"] = timeline_events
        return context

    def get_timeline_events(self):
        events = []

        work = self.object.metadata_json
        expressions = {
            point_in_time["date"]: point_in_time["expressions"][0]
            for point_in_time in work["points_in_time"]
        }

        if work["assent_date"]:
            events.append(
                {
                    "date": work["assent_date"],
                    "event": "assent",
                }
            )

        if work["publication_date"]:
            events.append(
                {
                    "date": work["publication_date"],
                    "event": "publication",
                }
            )

        if work["commencement_date"]:
            events.append(
                {
                    "date": work["commencement_date"],
                    "event": "commencement",
                }
            )

        events.extend(
            [
                {
                    "date": amendment["date"],
                    "event": "amendment",
                    "amending_title": amendment["amending_title"],
                    "amending_uri": amendment["amending_uri"],
                }
                for amendment in work["amendments"]
            ]
        )

        if work["repeal"]:
            events.append(
                {
                    "date": work["repeal"]["date"],
                    "event": "repeal",
                    "repealing_title": work["repeal"]["repealing_title"],
                    "repealing_uri": work["repeal"]["repealing_uri"],
                }
            )

        events.sort(key=lambda event: event["date"])
        events = [
            {
                "date": date,
                "events": list(group),
            }
            for date, group in groupby(events, lambda event: event["date"])
        ]

        for event in events:
            for e in event["events"]:
                del e["date"]
            uri = expressions.get(event["date"], {}).get("expression_frbr_uri")
            if uri:
                event["expression_frbr_uri"] = uri[4:]

        events.sort(key=lambda event: event["date"], reverse=True)

        return events
