from datetime import datetime, timedelta

from django.contrib import messages
from django.db.models import CharField, Func, Prefetch, Value
from django.db.models.functions.text import Substr
from django.http import Http404
from django.template.defaultfilters import date as format_date
from django.utils.decorators import method_decorator
from django.utils.html import mark_safe
from django.utils.translation import gettext as _
from django.views.generic import DetailView

from peachjam.forms import LegislationFilterForm, UnconstitutionalProvisionFilterForm
from peachjam.helpers import add_slash_to_frbr_uri
from peachjam.models import (
    CoreDocument,
    Legislation,
    ProvisionCitation,
    UncommencedProvision,
    UnconstitutionalProvision,
    pj_settings,
)
from peachjam.registry import registry
from peachjam.views.generic_views import (
    BaseDocumentDetailView,
    FilteredDocumentListView,
)


class LegislationListView(FilteredDocumentListView):
    model = Legislation
    template_name = "peachjam/legislation_list.html"
    navbar_link = "legislation"
    extra_context = {
        "nature": "Act",
        "help_link": "legislation/",
        "doc_table_show_date": False,
    }
    form_defaults = {"sort": "title"}
    form_class = LegislationFilterForm

    def add_facets(self, context):
        super().add_facets(context)
        # move the alphabet facet first, it's highly used on the legislation page for some LIIs
        if "alphabet" in context["facet_data"]:
            facets = {"alphabet": context["facet_data"].pop("alphabet")}
            for k, v in context["facet_data"].items():
                facets[k] = v
            context["facet_data"] = facets

    def add_years_facet(self, context):
        # for legislation, use the work year as the years facet
        if "years" not in self.exclude_facets:
            years = list(
                self.form.filter_queryset(self.get_base_queryset(), exclude="years")
                .order_by()
                .values_list(Substr("frbr_uri_date", 1, 4), flat=True)
                .distinct()
            )
            if years:
                context["facet_data"]["years"] = {
                    "label": _("Years"),
                    "type": "checkbox",
                    # these are (value, label) tuples
                    "options": [(str(y), y) for y in sorted(years, reverse=True)],
                    "values": self.request.GET.getlist("years"),
                }

    def get_document_group(self, group_by, document):
        if group_by == "frbr_uri_date":
            # use work year
            return document.frbr_uri_date[:4]
        return super().get_document_group(group_by, document)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["subleg_group_row"] = {
            "is_group": True,
            "title": pj_settings().subleg_label,
        }
        context["show_more_resources"] = (
            UnconstitutionalProvision.objects.exists()
            or UncommencedProvision.objects.exists()
        )
        context[
            "show_unconstitutional_provisions"
        ] = UnconstitutionalProvision.objects.exists()
        context["show_uncommenced_provisions"] = UncommencedProvision.objects.exists()
        return context


@registry.register_doc_type("legislation")
class LegislationDetailView(BaseDocumentDetailView):
    model = Legislation
    template_name = "peachjam/legislation_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["current_object_date"] = self.object.date.strftime("%Y-%m-%d")
        context["timeline"] = self.get_timeline()
        context["friendly_type"] = self.get_friendly_type()
        context["notices"] = self.get_notices()
        context["child_documents"] = self.get_child_documents()
        return context

    def get_notices(self):
        notices = super().get_notices()
        repeal = self.get_repeal_info()
        friendly_type = self.get_friendly_type()
        commenced, commenced_in_full = self.get_commencement_info()

        if self.object.metadata_json.get("disclaimer"):
            notices.append(
                {
                    "type": messages.WARNING,
                    "html": mark_safe(self.object.metadata_json.get("disclaimer")),
                }
            )

        if self.object.repealed and repeal:
            args = {"friendly_type": friendly_type}
            args.update(repeal)
            if repeal.get("repealing_uri"):
                notices.append(
                    {
                        "type": messages.ERROR,
                        "html": mark_safe(
                            _(
                                'This %(friendly_type)s was %(verb)s on %(date)s by <a href="%(repealing_uri)s">'
                                "%(repealing_title)s</a>."
                            )
                            % args
                        ),
                    }
                )
            else:
                notices.append(
                    {
                        "type": messages.ERROR,
                        "html": mark_safe(
                            _("This %(friendly_type)s %(verb)s on %(date)s.") % args
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
                        "html": _(
                            "This %(friendly_type)s will come into force on %(date)s."
                        )
                        % {
                            "friendly_type": friendly_type,
                            "date": format_date(latest_commencement_date, "j F Y"),
                        },
                    }
                )
            # don't overwhelm users with commencement notices -- only add this if
            # it is commenced in general, AND there isn't also a future commencement
            elif not commenced_in_full:
                notices.append(
                    {
                        "type": messages.WARNING,
                        "html": _(
                            "This %(friendly_type)s has not yet come into force in full."
                            " See the Uncommenced provisions tab for more information."
                        )
                        % {"friendly_type": friendly_type},
                    }
                )

        else:
            notices.append(
                {
                    "type": messages.WARNING,
                    "html": _("This %(friendly_type)s has not yet come into force.")
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

            try:
                index = point_in_time_dates.index(current_object_date)
            except ValueError:
                return notices

            if index == len(point_in_time_dates) - 1:
                if self.object.repealed and repeal:
                    if repeal["repealing_uri"]:
                        notices.append(
                            {
                                "type": messages.INFO,
                                "html": _(
                                    "This is the version of this %(friendly_type)s as it was when it was %(verb)s."
                                )
                                % {
                                    "friendly_type": friendly_type,
                                    "verb": repeal["verb"],
                                },
                            }
                        )
                    else:
                        notices.append(
                            {
                                "type": messages.INFO,
                                "html": _(
                                    "This is the version of this %(friendly_type)s as it was when it %(verb)s."
                                )
                                % {
                                    "friendly_type": friendly_type,
                                    "verb": repeal["verb"],
                                },
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
                    if repeal["repealing_uri"]:
                        msg = _(
                            "This is the version of this %(friendly_type)s as it was from %(date_from)s to %(date_to)s."
                            ' <a href="%(expression_frbr_uri)s">Read the version as it was when it was %(verb)s</a>.'
                        )
                    else:
                        msg = _(
                            "This is the version of this %(friendly_type)s as it was from %(date_from)s to %(date_to)s."
                            ' <a href="%(expression_frbr_uri)s">Read the version as it was when it %(verb)s</a>.'
                        )
                else:
                    msg = _(
                        "This is the version of this %(friendly_type)s as it was from %(date_from)s to %(date_to)s. "
                        ' <a href="%(expression_frbr_uri)s">Read the latest available version</a>.'
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
                                "verb": repeal["verb"] if repeal else "",
                            }
                        ),
                    }
                )

        if self.object.date > datetime.now().date():
            notices.append(
                {
                    "type": messages.WARNING,
                    "html": _("This version is at a future date."),
                }
            )

        return notices

    def get_repeal_info(self):
        repeal_info = self.object.metadata_json.get("repeal", None)
        if repeal_info and not repeal_info.get("verb"):
            repeal_info.update({"verb": "repealed"})
        return repeal_info

    def get_friendly_type(self):
        return self.object.metadata_json.get("type_name", None)

    def get_points_in_time(self):
        return self.object.metadata_json.get("points_in_time", [])

    def get_work_amendments(self):
        return self.object.metadata_json.get("work_amendments", None)

    def get_commencement_info(self):
        """Returns commenced, commenced_in_full.
        commenced_in_full defaults to True.
        """
        data = self.object.metadata_json
        return data.get("commenced"), data.get("commenced_in_full", True)

    def get_latest_commencement_date(self):
        commencement_dates = [
            commencement["date"]
            for commencement in self.object.metadata_json.get("commencements", []) or []
            if commencement["date"]
        ]
        if commencement_dates:
            return datetime.strptime(str(max(commencement_dates)), "%Y-%m-%d").date()
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
        points_in_time = self.get_points_in_time()

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
                # add contains_unapplied_amendment flag
                if event["type"] == "amendment":
                    entry["contains_unapplied_amendment"] = (
                        entry["date"] not in point_in_time_dates
                        and entry["date"] > latest_expression_date
                    )

        return timeline

    def get_child_documents(self):
        docs_ids = self.model.objects.filter(
            parent_work=self.object.work
        ).latest_expression()

        # now sort by title
        docs = (
            self.model.objects.filter(pk__in=docs_ids)
            .annotate(
                padded_frbr_uri_number=Func(
                    "frbr_uri_number",
                    Value(10),
                    Value("0"),
                    function="LPAD",
                    output_field=CharField(),
                )
            )
            .order_by("-date", "-frbr_uri_date", "-padded_frbr_uri_number")
            .for_document_table()
        )
        # TODO: we're not guaranteed to get documents in the same language, here
        return docs


class UncommencedProvisionDetailView(DetailView):
    model = UncommencedProvision
    template_name = "peachjam/provision_enrichment/uncommenced_provision_detail.html"
    context_object_name = "enrichment"


class DocumentUncommencedProvisionListView(DetailView):
    model = Legislation
    template_name = (
        "peachjam/provision_enrichment/_document_uncommenced_provision_list.html"
    )
    context_object_name = "document"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["uncommenced_provisions"] = self.object.work.enrichments.filter(
            enrichment_type="uncommenced_provision"
        )
        for enrichment in context["uncommenced_provisions"]:
            enrichment.document = self.object
        return context


class UncommencedProvisionListView(LegislationListView):
    template_name = "peachjam/provision_enrichment/uncommenced_provision_list.html"
    latest_expression_only = True

    def get_template_names(self):
        if self.request.htmx:
            if self.request.htmx.target == "doc-table":
                return ["peachjam/provision_enrichment/_uncommenced_table.html"]
            return ["peachjam/provision_enrichment/_uncommenced_table_form.html"]
        return super().get_template_names()

    def get_base_queryset(self, *args, **kwargs):
        qs = super().get_base_queryset(*args, **kwargs)
        uncommenced_provision_works = UncommencedProvision.objects.all().values_list(
            "work__id", flat=True
        )
        qs = qs.filter(work__in=uncommenced_provision_works)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["doc_table_show_counts"] = True
        return context


class UnconstitutionalProvisionListView(LegislationListView):
    template_name = "peachjam/provision_enrichment/unconstitutional_provision_list.html"
    latest_expression_only = True
    form_class = UnconstitutionalProvisionFilterForm
    exclude_facets = ["alphabet", "years"]

    def get_template_names(self):
        if self.request.htmx:
            if self.request.htmx.target == "doc-table":
                return ["peachjam/provision_enrichment/_table.html"]
            return ["peachjam/provision_enrichment/_table_form.html"]
        return super().get_template_names()

    def get_base_queryset(self, *args, **kwargs):
        qs = super().get_base_queryset(*args, **kwargs)
        unconstitutional_provision_works = (
            UnconstitutionalProvision.objects.all().values_list("work__id", flat=True)
        )
        qs = qs.filter(work__in=unconstitutional_provision_works)
        return qs

    def add_resolved_facet(self, context):
        # add a facet for resolved/unresolved at the top
        if "resolved" not in self.exclude_facets:
            context["facet_data"] = {
                "resolved": {
                    "label": _("Resolved"),
                    "type": "checkbox",
                    # these are (value, label) tuples
                    "options": [
                        ("resolved", _("Resolved")),
                        ("unresolved", _("Unresolved")),
                    ],
                    "values": self.request.GET.getlist("resolved"),
                },
                **context.get("facet_data", {}),
            }

    def add_facets(self, context):
        super().add_facets(context)
        self.add_resolved_facet(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        resolved_filter_values = self.request.GET.getlist("resolved")
        if (
            "resolved" in resolved_filter_values
            and "unresolved" in resolved_filter_values
        ):
            resolved_filter = "both"
        elif "resolved" in resolved_filter_values:
            resolved_filter = "resolved"
        elif "unresolved" in resolved_filter_values:
            resolved_filter = "unresolved"
        else:
            resolved_filter = "both"  # show nothing or default?
        for doc in context["documents"]:
            enrichments_qs = UnconstitutionalProvision.objects.filter(work=doc.work)

            if resolved_filter == "resolved":
                doc.provision_enrichments = enrichments_qs.filter(resolved=True)
            elif resolved_filter == "unresolved":
                doc.provision_enrichments = enrichments_qs.filter(resolved=False)
            elif resolved_filter == "both":
                doc.provision_enrichments = enrichments_qs.filter(
                    resolved__in=[True, False]
                )
            else:
                doc.provision_enrichments = enrichments_qs.all()

            # set the document on the enrichment objects so they know to use it for extra detail
            doc.provision_enrichments = list(doc.provision_enrichments)
            for enrichment in doc.provision_enrichments:
                enrichment.document = doc

        return context


@method_decorator(add_slash_to_frbr_uri(), name="setup")
class DocumentProvisionCitationView(FilteredDocumentListView):
    template_name = "peachjam/provision_enrichment/provision_citations.html"

    def get_template_names(self):
        if self.request.htmx:
            if self.request.htmx.target == "doc-table":
                return ["peachjam/provision_enrichment/_provision_citations_table.html"]
            return [
                "peachjam/provision_enrichment/_provision_citations_table_form.html"
            ]
        return super().get_template_names()

    @property
    def document(self):
        obj = CoreDocument.objects.filter(
            expression_frbr_uri=self.kwargs.get("frbr_uri")
        ).first()
        if not obj:
            raise Http404()

        # TODO: extract perms logic into a mixin
        if obj.restricted:
            perm = f"{obj._meta.app_label}.view_{obj._meta.model_name}"
            if not self.request.user.has_perm(perm, obj):
                raise Http404()
        return obj

    @property
    def provision_eid(self):
        return self.kwargs.get("provision_eid", "")

    @property
    def provision_citations(self):
        contexts = ProvisionCitation.objects.filter(
            work=self.document.work, provision_eid=self.provision_eid
        ).prefetch_related("work")
        if not contexts.exists():
            raise Http404("No citations found for this provision.")
        return contexts

    def get_base_queryset(self, *args, **kwargs):
        document_ids = self.provision_citations.values_list(
            "citing_document_id", flat=True
        )
        prefetch = Prefetch(
            "provision_citations",
            queryset=self.provision_citations,
            to_attr="relevant_provision_citations",
        )
        qs = (
            CoreDocument.objects.filter(pk__in=document_ids)
            .prefetch_related(prefetch)
            .for_document_table()
        )
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["document"] = self.document
        context["provision_title"] = context["document"].friendly_provision_title(
            self.provision_eid
        )
        context["provision_html"] = context["document"].get_provision_by_eid(
            self.provision_eid
        )
        context["citation_contexts"] = self.provision_citations
        return context
