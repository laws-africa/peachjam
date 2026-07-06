import string
from datetime import datetime, timedelta
from functools import cached_property
from types import SimpleNamespace
from urllib.parse import urlencode

from django.apps import apps
from django.contrib import messages
from django.db.models import CharField, Func, Prefetch, Value
from django.db.models.functions.text import Substr
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.template.defaultfilters import date as format_date
from django.urls import reverse
from django.utils import timezone
from django.utils.cache import add_never_cache_headers
from django.utils.decorators import method_decorator
from django.utils.html import mark_safe
from django.utils.translation import gettext as _
from django.views.generic import DetailView

from peachjam.forms import (
    LegislationFilterForm,
    UnconstitutionalProvisionFilterForm,
)
from peachjam.helpers import add_slash, add_slash_to_frbr_uri
from peachjam.models import (
    CoreDocument,
    Glossary,
    Legislation,
    ProvisionCitation,
    ProvisionCitationCount,
    UncommencedProvision,
    UnconstitutionalProvision,
    get_country_and_locality,
    pj_settings,
)
from peachjam.registry import registry
from peachjam.views.generic_views import (
    BaseDocumentDetailView,
    FilteredDocumentListView,
)
from peachjam_subs.mixins import PRIVATE_CACHE_MAX_AGE, SubscriptionRequiredMixin


class LegislationListView(FilteredDocumentListView):
    model = Legislation
    template_name = "peachjam/legislation_list.html"
    navbar_link = "legislation"
    extra_context = {
        "nature": "Act",
        "help_link": "legislation/finding-legislation",
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
        context["show_unconstitutional_provisions"] = (
            UnconstitutionalProvision.objects.exists()
        )
        context["show_uncommenced_provisions"] = UncommencedProvision.objects.exists()
        return context


class LegislationSubsidiaryView(LegislationListView):
    template_name = "peachjam/document/_legislation_subsidiary.html"
    latest_expression_only = True
    paginate_by = None

    def get_template_names(self):
        if self.request.htmx and self.request.htmx.target == "children-tab":
            return self.template_name
        return super().get_template_names()

    @cached_property
    def legislation(self):
        return get_object_or_404(
            Legislation,
            expression_frbr_uri=add_slash(self.kwargs.get("frbr_uri")),
        )

    def get_base_queryset(self):
        return Legislation.objects.filter(
            parent_work=self.legislation.work,
            published=True,
        ).for_document_table()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["legislation"] = self.legislation
        context["doc_table_show_date"] = False
        context["doc_table_disable_push_url"] = True
        context["doc_table_citations"] = True
        context["doc_table_show_jurisdiction"] = False
        context["doc_table_show_doc_type"] = False
        return context


@registry.register_doc_type("legislation")
class LegislationDetailView(SubscriptionRequiredMixin, BaseDocumentDetailView):
    model = Legislation
    template_name = "peachjam/legislation_detail.html"
    permission_required = "peachjam.can_view_historical_legislation"

    def get_object(self):
        # caching the object here to avoid multiple db hits
        if not hasattr(self, "_object"):
            self.object = super().get_object()
        return self.object

    def has_permission(self):
        obj = self.get_object()
        if obj.is_most_recent():
            return True
        return super().has_permission()

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)

        # Historical legislation should never be cached
        if hasattr(self, "object") and not self.object.is_most_recent():
            add_never_cache_headers(response)

        return response

    def get_subscription_required_template(self):
        return self.template_name

    def get_subscription_required_context(self):
        all_versions = CoreDocument.objects.filter(
            work_frbr_uri=self.object.work_frbr_uri
        )
        return {
            "document": self.object,
            "date_versions": all_versions.filter(
                language=self.object.language
            ).order_by("-date"),
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["current_object_date"] = self.object.date.strftime("%Y-%m-%d")
        context["timeline"] = self.get_timeline()
        context["friendly_type"] = self.get_friendly_type()
        context["notices"] = self.get_notices()
        context["child_documents_count"] = self.model.objects.filter(
            parent_work=self.object.work
        ).count()
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
        has_unapplied_amendments = self.has_unapplied_amendments(current_object_date)

        if not points_in_time and has_unapplied_amendments:
            self.set_unapplied_amendment_notice(notices)

        if points_in_time:
            point_in_time_dates = [
                point_in_time["date"] for point_in_time in points_in_time
            ]

            try:
                index = point_in_time_dates.index(current_object_date)
            except ValueError:
                return notices

            if index == len(point_in_time_dates) - 1:
                if work_amendments and self.object.repealed and repeal:
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

                elif has_unapplied_amendments:
                    self.set_unapplied_amendment_notice(notices)

                else:
                    # show latest notice even if no amendments
                    notices.append(
                        {
                            "type": messages.INFO,
                            "html": _(
                                "This is the latest version of this %(friendly_type)s."
                            )
                            % {"friendly_type": friendly_type},
                        }
                    )
            elif work_amendments:
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

    def has_unapplied_amendments(self, current_object_date):
        """Return true when an effective amendment has no matching expression."""
        today = timezone.localdate().strftime("%Y-%m-%d")
        point_in_time_dates = [p["date"] for p in self.get_points_in_time()]
        for amendment in self.get_work_amendments() or []:
            date = amendment.get("date")
            if (
                date
                and date <= today
                and date > current_object_date
                and date not in point_in_time_dates
            ):
                return True
        return False

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
        today = timezone.localdate().strftime("%Y-%m-%d")

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
                        and entry["date"] <= today
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


class UncommencedProvisionListView(SubscriptionRequiredMixin, LegislationListView):
    permission_required = "peachjam.view_uncommencedprovision"
    private_cache_max_age = PRIVATE_CACHE_MAX_AGE
    template_name = "peachjam/provision_enrichment/uncommenced_provision_list.html"
    document_table_template_name = (
        "peachjam/provision_enrichment/_uncommenced_table.html"
    )
    document_table_form_template_name = (
        "peachjam/provision_enrichment/_uncommenced_table_form.html"
    )
    latest_expression_only = True

    def get_subscription_required_template(self):
        return self.template_name

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


class UnconstitutionalProvisionDetailView(DetailView):
    model = UnconstitutionalProvision
    template_name = (
        "peachjam/provision_enrichment/unconstitutional_provision_detail.html"
    )
    context_object_name = "enrichment"


class UnconstitutionalProvisionListView(SubscriptionRequiredMixin, LegislationListView):
    permission_required = "peachjam.view_unconstitutionalprovision"
    private_cache_max_age = PRIVATE_CACHE_MAX_AGE
    template_name = "peachjam/provision_enrichment/unconstitutional_provision_list.html"
    document_table_template_name = (
        "peachjam/provision_enrichment/_unconstitutional_table.html"
    )
    document_table_form_template_name = (
        "peachjam/provision_enrichment/_unconstitutional_provisions_table_form.html"
    )
    latest_expression_only = True
    form_class = UnconstitutionalProvisionFilterForm
    exclude_facets = ["alphabet", "years"]

    def get_subscription_required_template(self):
        return self.template_name

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


class PlaceGlossaryView(SubscriptionRequiredMixin, DetailView):
    model = Glossary
    private_cache_max_age = PRIVATE_CACHE_MAX_AGE
    # this is expensive and is not used
    queryset = Glossary.objects.defer("data")
    slug_url_kwarg = "place_code"
    slug_field = "place_code"
    permission_required = "peachjam.view_glossary"
    template_name = "peachjam/glossary/glossary.html"

    def get_subscription_required_context(self):
        context = {"glossary": getattr(self, "object", self.get_object())}
        country, locality = get_country_and_locality(context["glossary"].place_code)
        context["place"] = locality or country
        return context

    def get_subscription_required_template(self):
        return self.template_name

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        letters = [*string.ascii_lowercase, "0"]
        context["letters"] = letters
        context.update(self.get_subscription_required_context())
        return context


class PlaceGlossaryLetterView(PlaceGlossaryView):
    template_name = "peachjam/glossary/_glossary_letter.html"
    queryset = Glossary.objects.all()
    letter = None

    def get(self, *args, **kwargs):
        self.letter = kwargs.get("letter")
        return super().get(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["letter"] = self.letter
        context["terms"] = self.object.data.get(self.letter, [])
        return context


class DocumentProvisionMixin:
    @cached_property
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

    def get_provision_context(self):
        return {
            "document": self.document,
            "provision_title": self.document.friendly_provision_title(
                self.provision_eid
            ),
            "provision_html": self.document.get_provision_by_eid(self.provision_eid),
            "provision_eid": self.provision_eid,
        }


class LegislationProvisionListView(LegislationListView):
    """A specialised form of LegislationListView that lists provisions of legislation.

    Subclasses should implement the logic to load provisions, and override prepare_provision to add any extra
    attributes to the provision objects that are needed for display.
    """

    document_table_template_name = "peachjam/document/_provisions_table.html"
    document_table_form_template_name = "peachjam/document/_provisions_table_form.html"

    def prepare_provision(self, document, provision):
        provision.document = document
        provision.title = self.get_provision_title(document, provision)
        provision.url = self.get_provision_url(document, provision)
        provision.compare_url = self.get_compare_url(document, provision)
        provision.provision_popup_url = self.get_provision_popup_url(
            document, provision
        )
        return provision

    def get_provision_title(self, document, provision):
        title = getattr(provision, "title", None)
        if title:
            return title
        if getattr(provision, "whole_work", False):
            return document.title
        provision_eid = getattr(provision, "provision_eid", None)
        if provision_eid:
            return document.friendly_provision_title(provision_eid)
        return document.title

    def get_provision_url(self, document, provision):
        provision_eid = getattr(provision, "provision_eid", None)
        if getattr(provision, "whole_work", False) or not provision_eid:
            return document.get_absolute_url()
        return f"{document.get_absolute_url()}#{provision_eid}"

    def get_compare_url(self, document, provision):
        provision_eid = getattr(provision, "provision_eid", None)
        if not provision_eid:
            return None
        params = {
            "uri-a": f"{document.expression_frbr_uri}/~{provision_eid}",
        }
        return f"{reverse('compare_portions')}?{urlencode(params)}"

    def get_provision_popup_url(self, document, provision):
        expression_frbr_uri = document.expression_frbr_uri
        if not expression_frbr_uri:
            return None

        frbr_uri = expression_frbr_uri.lstrip("/")
        provision_eid = getattr(provision, "provision_eid", None)
        if not getattr(provision, "whole_work", False) and provision_eid:
            frbr_uri = f"{frbr_uri}/~{provision_eid}"
        partner = self.request.get_host().split(":")[0]
        return reverse(
            "document_popup", kwargs={"partner": partner, "frbr_uri": frbr_uri}
        )


@method_decorator(add_slash_to_frbr_uri(), name="setup")
class DocumentProvisionCitationView(
    DocumentProvisionMixin, SubscriptionRequiredMixin, FilteredDocumentListView
):
    permission_required = "peachjam.view_provisioncitation"
    private_cache_max_age = PRIVATE_CACHE_MAX_AGE
    template_name = "peachjam/provision_enrichment/provision_citations.html"
    document_table_template_name = (
        "peachjam/provision_enrichment/_provision_citations_table.html"
    )
    document_table_form_template_name = (
        "peachjam/provision_enrichment/_provision_citations_table_form.html"
    )
    latest_expression_only = True

    def get_subscription_required_template(self):
        return self.template_name

    def get_subscription_required_context(self):
        return self.get_provision_context()

    @cached_property
    def provision_citations(self):
        contexts = ProvisionCitation.objects.filter(
            work=self.document.work, provision_eid=self.provision_eid
        ).prefetch_related("work")
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
        context.update(self.get_subscription_required_context())
        context["citation_contexts"] = self.provision_citations
        target_eid = self.provision_eid or None
        citing_documents_count = (
            ProvisionCitationCount.objects.filter(
                work=self.document.work, provision_eid=target_eid
            )
            .values_list("count", flat=True)
            .first()
        )
        context["citing_documents_count"] = citing_documents_count or 0
        return context


@method_decorator(add_slash_to_frbr_uri(), name="setup")
class DocumentProvisionSimilarView(
    DocumentProvisionMixin, SubscriptionRequiredMixin, LegislationProvisionListView
):
    # same permission as DocumentProvisionCitationView just to simplify things
    permission_required = "peachjam.view_provisioncitation"
    private_cache_max_age = PRIVATE_CACHE_MAX_AGE
    template_name = "peachjam/document/similar_provisions.html"
    latest_expression_only = True
    similarity_threshold = 0.8
    n_similar = 10
    exclude_facets = ["alphabet"]
    paginate_by = 0
    _similar_provisions = None

    def get_subscription_required_template(self):
        return self.template_name

    def get_subscription_required_context(self):
        return self.get_provision_context()

    def get_base_queryset(self, *args, **kwargs):
        if not apps.is_installed("peachjam_ml"):
            return self.model.objects.none()

        qs = super().get_base_queryset(*args, **kwargs)
        qs = qs.exclude(work=self.document.work)
        return qs.filter(pk__in=self.get_similar_document_ids(qs))

    def get_similar_document_ids(self, documents_qs):
        return {
            provision["document_id"]
            for provision in self.get_similar_provisions(documents_qs)
        }

    def get_similar_provisions(self, documents_qs):
        if not apps.is_installed("peachjam_ml"):
            return []

        # simple cache, since this is expensive
        if self._similar_provisions is None:
            from peachjam_ml.models import ContentChunk

            self._similar_provisions = ContentChunk.get_similar_provisions(
                self.document,
                self.provision_eid,
                documents_qs,
                threshold=self.similarity_threshold,
                n_similar=self.n_similar,
            )

        return self._similar_provisions

    def prepare_provision(self, document, provision):
        portion_id = provision["portion"]
        return super().prepare_provision(
            document,
            SimpleNamespace(
                provision_eid=portion_id,
                portion_id=portion_id,
                title=provision["title"],
                similarity=provision["similarity"],
            ),
        )

    def get_compare_url(self, document, provision):
        params = {
            "uri-a": f"{self.document.expression_frbr_uri}/~{self.provision_eid}",
            "uri-b": f"{document.expression_frbr_uri}/~{provision.provision_eid}",
        }
        return f"{reverse('compare_portions')}?{urlencode(params)}"

    def get_provision_title(self, document, provision):
        return provision.title or document.friendly_provision_title(
            provision.provision_eid
        )

    def decorate_documents_with_similar_provisions(self, documents):
        similar_provisions = self.get_similar_provisions(documents)
        if not similar_provisions:
            return

        document_map = {document.pk: document for document in documents}

        results = []
        for provision in similar_provisions:
            document = document_map.get(provision["document_id"])
            if not document:
                continue

            if not hasattr(document, "provisions"):
                document.provisions = []
                results.append(document)
            document.provisions.append(self.prepare_provision(document, provision))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_subscription_required_context())
        self.decorate_documents_with_similar_provisions(context["documents"])
        context["doc_count_noun"] = _("document with similar provisions")
        context["doc_count_noun_plural"] = _("documents with similar provisions")
        return context
