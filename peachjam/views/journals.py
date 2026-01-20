from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from peachjam.forms import JournalArticleFilterForm
from peachjam.helpers import chunks
from peachjam.models import Journal, JournalArticle, VolumeIssue
from peachjam.registry import registry
from peachjam.views.generic_views import (
    BaseDocumentDetailView,
    FilteredDocumentListView,
)


def ensure_volume_slugs(volumes):
    for volume in volumes:
        slug = (volume.slug or "").strip().lower()
        if not slug or slug in {"none", "null"}:
            volume.slug = slugify(volume.title)
            volume.save(update_fields=["slug"])


class JournalListView(TemplateView):
    template_name = "peachjam/journal_list.html"
    navbar_link = "journals"

    def get_journals(self):
        return (
            Journal.objects.annotate(
                article_count=Count("articles", filter=Q(articles__published=True))
            )
            .prefetch_related("volumes")
            .order_by("title")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        journals = self.get_journals()
        for journal in journals:
            volumes = list(journal.volumes.all())
            journal.volume_groups = chunks(volumes, 3)
        context["journals"] = journals
        context["journal_count"] = journals.count()
        return context


class VolumeIssueListView(TemplateView):
    template_name = "peachjam/volume_list.html"
    navbar_link = "journals"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        journal = get_object_or_404(Journal, slug=self.kwargs["slug"])
        volume_issues = list(
            VolumeIssue.objects.select_related("journal")
            .filter(journal=journal)
            .order_by("-year", "title")
        )
        ensure_volume_slugs(volume_issues)
        context["volume_issues"] = volume_issues
        context["volume_issue_count"] = len(volume_issues)
        context["journal"] = journal
        return context


class VolumeIssueDetailView(FilteredDocumentListView):
    model = JournalArticle
    template_name = "peachjam/volume_detail.html"
    navbar_link = "journals"
    form_class = JournalArticleFilterForm

    def get_base_queryset(self, *args, **kwargs):
        self.journal = get_object_or_404(Journal, slug=self.kwargs["slug"])
        volume_qs = VolumeIssue.objects.select_related("journal").filter(
            journal=self.journal, slug=self.kwargs["volume_slug"]
        )
        self.volume_issue = volume_qs.order_by("pk").first()
        if not self.volume_issue:
            raise Http404()
        return super().get_base_queryset().filter(volume=self.volume_issue)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["volume_issue"] = self.volume_issue
        context["journal"] = self.journal
        context["doc_count_noun"] = _("journal article")
        context["doc_count_noun_plural"] = _("journal articles")
        context["nature"] = "Journal article"
        context["help_link"] = "journals"
        return context


class JournalArticleListView(FilteredDocumentListView):
    model = JournalArticle
    template_name = "peachjam/journal_article_list.html"
    navbar_link = "journals"
    form_class = JournalArticleFilterForm

    def get_base_queryset(self, *args, **kwargs):
        queryset = super().get_base_queryset(*args, **kwargs)
        self.journal = None
        slug = self.kwargs.get("slug")
        if slug:
            self.journal = get_object_or_404(
                Journal.objects.prefetch_related("volumes"), slug=slug
            )
            queryset = queryset.filter(journal=self.journal)
        return queryset

    def add_facets(self, context):
        super().add_facets(context)
        journals = list(
            self.form.filter_queryset(self.get_base_queryset(), exclude="journals")
            .filter(journal__isnull=False)
            .order_by("journal__title")
            .values_list("journal__id", "journal__title")
            .distinct()
        )
        if journals:
            context["facet_data"] = {
                "journals": {
                    "label": _("Journals"),
                    "type": "checkbox",
                    "options": [
                        (str(journal_id), title) for journal_id, title in journals
                    ],
                    "values": self.request.GET.getlist("journals"),
                },
                **context["facet_data"],
            }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["doc_count_noun"] = _("journal article")
        context["doc_count_noun_plural"] = _("journal articles")
        context["nature"] = "Journal article"
        context["help_link"] = "journals"
        context["journal"] = self.journal
        if self.journal:
            volumes = list(self.journal.volumes.all())
            ensure_volume_slugs(volumes)
            context["volume_groups"] = chunks(volumes, 3)
        return context


@registry.register_doc_type("journal_article")
class JournalArticleDetailView(BaseDocumentDetailView):
    model = JournalArticle
    template_name = "peachjam/journal_article_detail.html"


class JournalArticleSlugDetailView(BaseDocumentDetailView):
    model = JournalArticle
    template_name = "peachjam/journal_article_detail.html"

    def get_object(self, *args, **kwargs):
        return get_object_or_404(self.model, slug=self.kwargs["slug"])

    def get_queryset(self):
        return super().get_queryset().select_related("journal", "volume")
