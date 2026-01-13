from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from peachjam.forms import JournalArticleFilterForm
from peachjam.models import Book, Journal, JournalArticle, VolumeIssue
from peachjam.registry import registry
from peachjam.views.generic_views import (
    BaseDocumentDetailView,
    FilteredDocumentListView,
)


class BookListView(FilteredDocumentListView):
    queryset = Book.objects.all()
    model = Book
    template_name = "peachjam/book_list.html"
    navbar_link = "books"


@registry.register_doc_type("book")
class BookDetailView(BaseDocumentDetailView):
    model = Book
    template_name = "peachjam/book_detail.html"


class JournalListView(TemplateView):
    template_name = "peachjam/journal_list.html"
    navbar_link = "journals"

    def get_journals(self):
        return Journal.objects.annotate(
            article_count=Count("articles", filter=Q(articles__published=True))
        ).order_by("title")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        journals = self.get_journals()
        context["journals"] = journals
        context["journal_count"] = journals.count()
        return context


class VolumeIssueListView(TemplateView):
    template_name = "peachjam/volumes_list.html"
    navbar_link = "journals"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        volume_issues = VolumeIssue.objects.select_related("journal").order_by(
            "journal__title", "-year", "title"
        )
        context["volume_issues"] = volume_issues
        context["volume_issue_count"] = volume_issues.count()
        return context


class VolumeIssueDetailView(FilteredDocumentListView):
    model = JournalArticle
    template_name = "peachjam/volume_detail.html"
    navbar_link = "journals"
    form_class = JournalArticleFilterForm

    def get_base_queryset(self, *args, **kwargs):
        self.volume_issue = get_object_or_404(
            VolumeIssue.objects.select_related("journal"), pk=self.kwargs["pk"]
        )
        return super().get_base_queryset().filter(volume=self.volume_issue)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["volume_issue"] = self.volume_issue
        context["doc_count_noun"] = _("journal article")
        context["doc_count_noun_plural"] = _("journal articles")
        context["nature"] = "Journal article"
        context["help_link"] = "journals"
        return context


class JournalArticleListView(FilteredDocumentListView):
    model = JournalArticle
    template_name = "peachjam/journal_articles_list.html"
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
        context["doc_count_noun"] = _("journal article")
        context["doc_count_noun_plural"] = _("journal articles")
        context["nature"] = "Journal article"
        context["help_link"] = "journals"
        return context


@registry.register_doc_type("journal_article")
class JournalArticleDetailView(BaseDocumentDetailView):
    model = JournalArticle
