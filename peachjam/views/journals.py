from django.db.models import Count, Max, Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from django.views.generic import ListView

from peachjam.forms import JournalArticleFilterForm
from peachjam.helpers import chunks
from peachjam.models import Journal, JournalArticle, VolumeIssue
from peachjam.registry import registry
from peachjam.views.generic_views import (
    BaseDocumentDetailView,
    FilteredDocumentListView,
)


class JournalListView(ListView):
    template_name = "peachjam/journal/journal_list.html"
    navbar_link = "journals"
    model = Journal
    context_object_name = "journals"

    def get_queryset(self):
        return (
            self.model.objects.annotate(
                article_count=Count("articles", filter=Q(articles__published=True)),
                latest_article_created_at=Max(
                    "articles__created_at", filter=Q(articles__published=True)
                ),
            )
            .prefetch_related("volumes")
            .order_by("title")
        )


class VolumeIssueDetailView(FilteredDocumentListView):
    model = JournalArticle
    template_name = "peachjam/journal/volume_detail.html"
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
        context["doc_count_noun"] = _("Article")
        context["doc_count_noun_plural"] = _("Articles")
        context["nature"] = "Journal article"
        context["help_link"] = "journals"
        return context


class JournalArticleListView(FilteredDocumentListView):
    model = JournalArticle
    template_name = "peachjam/journal/journal_article_list.html"
    navbar_link = "journals"
    form_class = JournalArticleFilterForm

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
        context["doc_count_noun"] = _("Article")
        context["doc_count_noun_plural"] = _("Articles")
        context["nature"] = "Article"
        context["help_link"] = "journals"
        return context


class JournalDetailView(JournalArticleListView):
    template_name = "peachjam/journal/journal_detail.html"

    def get_object(self):
        self.journal = get_object_or_404(
            Journal.objects.prefetch_related("volumes"), slug=self.kwargs["slug"]
        )
        return self.journal

    def get(self, request, *args, **kwargs):
        self.get_object()
        return super().get(request, *args, **kwargs)

    def get_base_queryset(self, *args, **kwargs):
        queryset = super().get_base_queryset(*args, **kwargs)
        return queryset.filter(journal=self.journal)

    def add_facets(self, context):
        super().add_facets(context)
        context["facet_data"].pop("journals", None)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["hide_follow_button"] = True
        context["entity_profile"] = self.journal.entity_profile.first()
        context["journal"] = self.journal
        volumes = list(self.journal.volumes.all())
        context["volume_groups"] = chunks(volumes, 3)
        return context


@registry.register_doc_type("journal_article")
class JournalArticleDetailView(BaseDocumentDetailView):
    model = JournalArticle
    template_name = "peachjam/journal/journal_article_detail.html"


class JournalArticleSlugDetailView(BaseDocumentDetailView):
    model = JournalArticle
    template_name = "peachjam/journal/journal_article_detail.html"

    def get_object(self, *args, **kwargs):
        return get_object_or_404(self.model, slug=self.kwargs["slug"])

    def get_queryset(self):
        return super().get_queryset().select_related("journal", "volume")
