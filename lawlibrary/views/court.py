from django.shortcuts import get_object_or_404

from africanlii.utils import lowercase_alphabet
from peachjam.models import Author, Judgment
from peachjam.views.generic_views import FilteredDocumentListView


class CourtDetailView(FilteredDocumentListView):
    context_object_name = "documents"
    paginate_by = 20
    model = Judgment
    template_name = "lawlibrary/court_detail.html"

    def get_base_queryset(self):
        return self.model.objects.filter(author=self.author)

    def get_queryset(self):
        self.author = get_object_or_404(Author, code=self.kwargs["code"])
        return super().get_queryset()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        years = list(
            set(
                self.model.objects.filter(author=self.author).values_list(
                    "date__year", flat=True
                )
            )
        )

        context["years"] = sorted(years, reverse=True)

        judges = list(
            set(
                self.model.objects.filter(author=self.author).values_list(
                    "judges__name", flat=True
                )
            )
        )
        if None in judges:
            judges.remove(None)

        context["court"] = self.author
        context["judgments"] = self.author.judgment_set.all()
        context["facet_data"] = {
            "authors": judges,
            "years": years,
            "alphabet": lowercase_alphabet(),
        }

        return context


class YearView(FilteredDocumentListView):
    template_name = "lawlibrary/court_detail.html"
    context_object_name = "documents"
    model = Judgment

    def get_base_queryset(self):
        return self.model.objects.filter(author=self.author)

    def get_queryset(self):
        self.author = get_object_or_404(Author, code=self.kwargs["code"])
        return super().get_queryset()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        years = list(
            set(
                self.model.objects.filter(author=self.author).values_list(
                    "date__year", flat=True
                )
            )
        )

        judges = list(
            set(
                self.model.objects.filter(author=self.author).values_list(
                    "judges__name", flat=True
                )
            )
        )
        if None in judges:
            judges.remove(None)

        context["court"] = self.author
        context["judgments"] = Judgment.objects.filter(
            author=self.author, date__year=self.kwargs["year"]
        )

        context["years"] = sorted(years, reverse=True)

        context["facet_data"] = {
            "authors": judges,
            "years": years,
            "alphabet": lowercase_alphabet(),
        }

        return context
