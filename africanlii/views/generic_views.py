from django.views.generic import ListView

from africanlii.forms import BaseDocumentFilterForm
from africanlii.models import AuthoringBody, Court


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
