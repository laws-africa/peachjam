from django.views.generic import ListView

from africanlii.forms import BaseDocumentFilterForm


class FilteredDocumentListView(ListView, BaseDocumentFilterForm):
    """Generic List View class for filtering documents."""

    def get_queryset(self):
        self.form = BaseDocumentFilterForm(self.request.GET)
        self.form.is_valid()
        queryset = self.model.objects.all()
        return self.form.filter_queryset(queryset)

    def get_context_data(self, **kwargs):
        context = super(FilteredDocumentListView, self).get_context_data(**kwargs)
        years = list(
            set(
                self.model.objects.values_list("date__year", flat=True)
                .order_by()
                .distinct()
            )
        )
        context["facet_data"] = {
            "years": years,
            "authors": [
                {"name": "Hope", "id": 1},
                {
                    "name": "Kain",
                    "id": 2,
                },
                {"name": "Jen", "id": 3},
                {"name": "Musango", "id": 4},
            ],
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
