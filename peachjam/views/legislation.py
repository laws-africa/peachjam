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
    queryset = Legislation.objects.prefetch_related("work")


@registry.register_doc_type("legislation")
class LegislationDetailView(BaseDocumentDetailView):
    model = Legislation
    template_name = "peachjam/legislation_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["current_object_date"] = self.object.date.strftime("%Y-%m-%d")
        context["timeline"] = self.get_timeline()
        # TODO: get rid of timeline_events once all Legislation objects have been re-ingested
        context["timeline_events"] = self.get_timeline_events()
        context["friendly_type"] = self.get_friendly_type()
        context["notices"] = self.get_notices()
        context["child_documents"] = self.get_child_documents()
        return context

    def get_notices(self):
        notices = super().get_notices()
        repeal = self.get_repeal_info()
        friendly_type = self.get_friendly_type()
        commenced = self.get_commencement_info()

        if self.object.repealed and repeal:
            args = {"friendly_type": friendly_type}
            args.update(repeal)
            notices.append(
                {
                    "type": messages.ERROR,
                    "html": mark_safe(
                        _(
                            'This %(friendly_type)s was repealed on %(date)s by <a href="%(repealing_uri)s">'
                            "%(repealing_title)s</a>."
                        )
                        % args
                    ),
                }
            )

        current_date = datetime.now().date()
        latest_commencement_date = self.get_latest_commencement_date()
        if commenced:
            if latest_commencement_date and latest_commencement_date > current_date:
                notices.append(
                    {
                        "type": messages.WARNING,
                        "html": _("This %(friendly_type)s will commence on %(date)s.")
                        % {
                            "friendly_type": friendly_type,
                            "date": format_date(latest_commencement_date, "j F Y"),
                        },
                    }
                )

        else:
            notices.append(
                {
                    "type": messages.WARNING,
                    "html": _(
                        "This %(friendly_type)s has not yet commenced and is not yet law."
                    )
                    % {"friendly_type": friendly_type},
                }
            )

        points_in_time = self.get_points_in_time()
        work_amendments = self.get_work_amendments()
        current_object_date = self.object.date.strftime("%Y-%m-%d")

        if not work_amendments:
            latest_amendment_date = None
        else:
            work_amendments_dates = [
                work_amendment["date"] for work_amendment in work_amendments
            ]
            latest_amendment_date = max(work_amendments_dates)

            if not points_in_time and latest_amendment_date > current_object_date:
                self.set_unapplied_amendment_notice(notices)

        if points_in_time and work_amendments:
            point_in_time_dates = [
                point_in_time["date"] for point_in_time in points_in_time
            ]

            index = point_in_time_dates.index(current_object_date)

            if index == len(point_in_time_dates) - 1:
                if self.object.repealed and repeal:
                    notices.append(
                        {
                            "type": messages.INFO,
                            "html": _(
                                "This is the version of this %(friendly_type)s as it was when it was repealed."
                            )
                            % {"friendly_type": friendly_type},
                        }
                    )

                elif work_amendments and latest_amendment_date > current_object_date:
                    self.set_unapplied_amendment_notice(notices)

                else:
                    notices.append(
                        {
                            "type": messages.INFO,
                            "html": _(
                                "This is the latest version of this %(friendly_type)s."
                            )
                            % {"friendly_type": friendly_type},
                        }
                    )
            else:
                date = datetime.strptime(
                    point_in_time_dates[index + 1], "%Y-%m-%d"
                ).date() - timedelta(days=1)
                expression_frbr_uri = points_in_time[-1]["expressions"][0][
                    "expression_frbr_uri"
                ]

                if self.object.repealed and repeal:
                    msg = _(
                        "This is the version of this %(friendly_type)s as it was from %(date_from)s to %(date_to)s. "
                        ' <a href="%(expression_frbr_uri)s">Read the version as it was when it was repealed</a>.'
                    )
                else:
                    msg = _(
                        "This is the version of this %(friendly_type)s as it was from %(date_from)s to %(date_to)s. "
                        ' <a href="%(expression_frbr_uri)s">Read the version currently in force</a>.'
                    )

                notices.append(
                    {
                        "type": messages.WARNING,
                        "html": mark_safe(
                            msg
                            % {
                                "date_from": format_date(self.object.date, "j F Y"),
                                "date_to": format_date(date, "j F Y"),
                                "expression_frbr_uri": expression_frbr_uri,
                                "friendly_type": friendly_type,
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
        return self.object.metadata_json.get("points_in_time", [])

    def get_work_amendments(self):
        return self.object.metadata_json.get("work_amendments", None)

    def get_commencement_info(self):
        return self.object.metadata_json.get("commenced", None)

    def get_latest_commencement_date(self):
        commencements = self.object.metadata_json.get("commencements", None)
        if commencements:
            commencement_dates = [
                commencement["date"] for commencement in commencements
            ]
            return datetime.strptime(max(commencement_dates), "%Y-%m-%d").date()

        return None

    def set_unapplied_amendment_notice(self, notices):
        notices.append(
            {
                "type": messages.WARNING,
                "html": _(
                    "There are outstanding amendments that have not yet been applied. "
                    "See the History tab for more information."
                ),
            }
        )

    def get_timeline(self):
        timeline = self.object.timeline_json
        publication_url = None
        work = self.object.metadata_json
        points_in_time = self.get_points_in_time()

        # set publication_url
        publication_date = work.get("publication_date")
        if publication_date:
            # TODO: update to v3 throughout
            api_url = "https://api.laws.africa/v2/"
            commons_url = "https://commons.laws.africa/"
            publication_url = (work.get("publication_document") or {}).get("url")
            if publication_url and api_url in publication_url:
                publication_url = publication_url.replace(api_url, commons_url)

        # prepare for setting contains_unapplied_amendment flag
        point_in_time_dates = [p["date"] for p in points_in_time]
        latest_expression_date = (
            max(point_in_time_dates)
            if point_in_time_dates
            else self.object.date.strftime("%Y-%m-%d")
        )

        # fold in links to expressions corresponding to each event date (if any)
        # TODO: match on language rather than using first expression?
        expression_uris = {
            point_in_time["date"]: point_in_time["expressions"][0][
                "expression_frbr_uri"
            ]
            for point_in_time in points_in_time
        }

        for entry in timeline:
            # add expression_frbr_uri
            for event in entry["events"]:
                entry["expression_frbr_uri"] = expression_uris.get(entry["date"])
                # add publication_url to publication event
                if event["type"] == "publication":
                    event["link_url"] = publication_url
                # add contains_unapplied_amendment flag
                if event["type"] == "amendment":
                    entry["contains_unapplied_amendment"] = (
                        entry["date"] not in point_in_time_dates
                        and entry["date"] > latest_expression_date
                    )

        return timeline

    def get_timeline_events(self):
        events = []
        work = self.object.metadata_json

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
            publication_url = (work.get("publication_document") or {}).get("url")
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

        points_in_time = self.get_points_in_time()

        amendments = self.get_work_amendments()
        if amendments:
            point_in_time_dates = [
                point_in_time["date"] for point_in_time in points_in_time
            ]
            latest_expression_date = (
                max(point_in_time_dates)
                if point_in_time_dates
                else self.object.date.strftime("%Y-%m-%d")
            )

            events.extend(
                [
                    {
                        "date": amendment.get("date"),
                        "event": "amendment",
                        "amending_title": amendment.get("amending_title"),
                        "amending_uri": amendment.get("amending_uri"),
                        "unapplied_amendment": bool(
                            amendment.get("date") not in point_in_time_dates
                            and amendment.get("date") > latest_expression_date
                        ),
                    }
                    for amendment in amendments
                ]
            )

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

        # fold in links to expressions corresponding to each event date (if any)
        expressions = {
            point_in_time["date"]: point_in_time["expressions"][0]
            for point_in_time in points_in_time
        }
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
