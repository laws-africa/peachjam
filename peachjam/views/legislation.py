from datetime import datetime, timedelta
from itertools import groupby

from django.contrib import messages
from django.template.defaultfilters import date as format_date
from django.utils.html import mark_safe
from django.utils.translation import gettext as _

from peachjam.models import Legislation
from peachjam.registry import registry
from peachjam.views.generic_views import (
    BaseDocumentDetailView,
    FilteredDocumentListView,
)


class LegislationListView(FilteredDocumentListView):
    model = Legislation
    template_name = "peachjam/legislation_list.html"
    navbar_link = "legislation"


@registry.register_doc_type("legislation")
class LegislationDetailView(BaseDocumentDetailView):
    model = Legislation
    template_name = "peachjam/legislation_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["current_object_date"] = self.object.date.strftime("%Y-%m-%d")
        context["timeline_events"] = self.get_timeline_events()
        context["friendly_type"] = self.get_friendly_type()
        context["notices"] = self.get_notices()
        context["child_documents"] = self.get_child_documents()
        return context

    def get_notices(self):
        notices = super().get_notices()
        repeal = self.get_repeal_info()
        friendly_type = self.get_friendly_type()

        if self.object.repealed and repeal:
            msg = (
                f'This {friendly_type} was repealed on %(date)s by <a href="%(repealing_uri)s">'
                "%(repealing_title)s</a>."
            )
            notices.append(
                {
                    "type": messages.ERROR,
                    "html": mark_safe(_(msg) % repeal),
                }
            )

        points_in_time = self.get_points_in_time()
        work_amendments = self.get_work_amendments()

        if points_in_time:
            current_object_date = self.object.date.strftime("%Y-%m-%d")
            point_in_time_dates = [
                point_in_time["date"] for point_in_time in points_in_time
            ]
            work_amendments_dates = [
                work_amendment["date"] for work_amendment in work_amendments
            ]
            latest_amendment_date = work_amendments_dates[-1]
            index = point_in_time_dates.index(current_object_date)

            if index == len(point_in_time_dates) - 1:
                if self.object.repealed and repeal:
                    msg = f"This is the version of this {friendly_type} as it was when it was repealed."
                    notices.append(
                        {
                            "type": messages.INFO,
                            "html": _(msg),
                        }
                    )

                elif work_amendments and latest_amendment_date > current_object_date:
                    msg = (
                        f"This is the latest available version of this {friendly_type}. "
                        f"There are outstanding amendments that have not yet been applied. "
                        f"See the History tab for more information."
                    )
                    notices.append(
                        {
                            "type": messages.WARNING,
                            "html": _(msg),
                        }
                    )

                else:
                    msg = f"This is the latest version of this {friendly_type}."
                    notices.append(
                        {
                            "type": messages.INFO,
                            "html": _(msg),
                        }
                    )
            else:
                date = datetime.strptime(
                    point_in_time_dates[index + 1], "%Y-%m-%d"
                ).date() - timedelta(days=1)
                expression_frbr_uri = points_in_time[-1]["expressions"][0][
                    "expression_frbr_uri"
                ]

                msg = f"This is the version of this {friendly_type} as it was from %(date_from)s to %(date_to)s."
                if self.object.repealed and repeal:
                    msg += ' <a href="%(expression_frbr_uri)s">Read the version as it was when it was repealed</a>.'
                else:
                    msg += ' <a href="%(expression_frbr_uri)s">Read the version currently in force</a>.'

                notices.append(
                    {
                        "type": messages.WARNING,
                        "html": mark_safe(
                            _(msg)
                            % {
                                "date_from": format_date(self.object.date, "j F Y"),
                                "date_to": format_date(date, "j F Y"),
                                "expression_frbr_uri": expression_frbr_uri,
                            }
                        ),
                    }
                )

        return notices

    def get_repeal_info(self):
        return self.object.metadata_json.get("repeal", None)

    def get_friendly_type(self):
        return self.object.metadata_json.get("type_name", None)

    def get_points_in_time(self):
        return self.object.metadata_json.get("points_in_time", None)

    def get_work_amendments(self):
        return self.object.metadata_json.get("work_amendments", None)

    def get_timeline_events(self):
        events = []

        work = self.object.metadata_json

        points_in_time = self.get_points_in_time()
        expressions = {
            point_in_time["date"]: point_in_time["expressions"][0]
            for point_in_time in points_in_time or []
        }

        assent_date = self.object.metadata_json.get("assent_date", None)
        if assent_date:
            events.append(
                {
                    "date": work.get("assent_date"),
                    "event": "assent",
                }
            )

        publication_date = self.object.metadata_json.get("publication_date", None)
        if publication_date:
            api_url = "https://api.laws.africa/v2/"
            commons_url = "https://commons.laws.africa/"
            publication_url = work.get("publication_document", {}).get("url")
            if publication_url and api_url in publication_url:
                publication_url = publication_url.replace(api_url, commons_url)

            events.append(
                {
                    "date": publication_date,
                    "event": "publication",
                    "publication_name": work.get("publication_name"),
                    "publication_number": work.get("publication_number"),
                    "publication_url": publication_url,
                }
            )

        commencement_date = self.object.metadata_json.get("commencement_date", None)
        if commencement_date:
            events.append(
                {
                    "date": commencement_date,
                    "event": "commencement",
                    "friendly_type": work.get("type_name"),
                }
            )

        amendments = self.get_work_amendments()
        if points_in_time and amendments:
            point_in_time_dates = [
                point_in_time["date"] for point_in_time in points_in_time
            ]
            event = [
                {
                    "date": amendment.get("date"),
                    "event": "amendment",
                    "amending_title": amendment.get("amending_title"),
                    "amending_uri": amendment.get("amending_uri"),
                    "unapplied_amendment": bool(
                        amendment.get("date") not in point_in_time_dates
                    ),
                }
                for amendment in amendments
            ]

            events.extend(event)

        repeal = self.get_repeal_info()
        if repeal:
            events.append(
                {
                    "date": repeal.get("date"),
                    "event": "repeal",
                    "repealing_title": repeal.get("repealing_title"),
                    "repealing_uri": repeal.get("repealing_uri"),
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
                event["expression_frbr_uri"] = uri

        events.sort(key=lambda event: event["date"], reverse=True)

        return events

    def get_child_documents(self):
        docs = (
            self.model.objects.filter(parent_work=self.object.work)
            .distinct("work_frbr_uri")
            .order_by("work_frbr_uri", "-date")
        )
        # now sort by title
        # TODO: we're not guaranteed to get documents in the same language, here
        docs = sorted(docs, key=lambda d: d.title)
        return docs


# Translation strings that include the friendly document type to ensure we have translations for the full string.
_("This is the version of this Act as it was when it was repealed.")
_("This is the latest version of this Act.")
_(
    'This Act was repealed on %(date)s by <a href="%(repealing_uri)s">%(repealing_title)s</a>.'
)
_(
    'This is the version of this Act as it was from %(date_from)s to %(date_to)s. <a href="%(expression_frbr_uri)s">'
    "Read the version as it was when it was repealed</a>."
)
_(
    'This is the version of this Act as it was from %(date_from)s to %(date_to)s. <a href="%(expression_frbr_uri)s">'
    "Read the version currently in force</a>."
)
