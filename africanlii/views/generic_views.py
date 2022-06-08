from django.views.generic import ListView

from africanlii.forms import BaseDocumentFilterForm
from africanlii.models import AuthoringBody, Court
from peachjam.models import CoreDocument


class FilteredDocumentListView(ListView, BaseDocumentFilterForm):
    """Generic List View class for filtering documents."""

    def get_queryset(self):
        self.form = BaseDocumentFilterForm(self.request.GET)
        self.form.is_valid()
        queryset = self.model.objects.all()
        return self.form.filter_queryset(queryset)

    def get_context_data(self, **kwargs):
        context = super(FilteredDocumentListView, self).get_context_data(**kwargs)
        years = list(set(self.model.objects.values_list("date__year", flat=True)))
        courts = list(Court.objects.values_list("name", flat=True))
        authoring_bodies = list(AuthoringBody.objects.values_list("name", flat=True))

        context["facet_data"] = {
            "years": years,
            "courts": courts,
            "authoring_bodies": authoring_bodies,
            "alphabet": [
                "a",
                "b",
                "c",
                "d",
                "e",
                "f",
                "g",
                "h",
                "i",
                "j",
                "k",
                "l",
                "m",
                "n",
                "o",
                "p",
                "q",
                "r",
                "s",
                "t",
                "u",
                "v",
                "w",
                "x",
                "y",
                "z",
            ],
        }
        return context


class DocumentVersionsMixin:
    """Helper mixin for document detail views to fetch other versions of a document based
    on the document's work_frbr_uri and separate them based on language and date.
    """

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # get all versions that match current document work_frbr_uri
        all_versions = CoreDocument.objects.filter(
            work_frbr_uri=self.object.work_frbr_uri
        ).exclude(pk=self.object.pk)

        # language versions that match current document date
        context["language_versions"] = all_versions.filter(date=self.object.date)

        # date versions that match current document language
        context["date_versions"] = all_versions.filter(language=self.object.language)

        return context
