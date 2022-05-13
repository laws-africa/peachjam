from django import forms
from django.db.models import Q


class DocumentFilterForm(forms.Form):
    """This is the main form used for filtering Document ListViews, using facets such as year,
    author and alphabetical title.
    """

    author = forms.ChoiceField(required=False)
    alphabet = forms.CharField(required=False)
    year = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def is_valid_queryparam(self, param):
        return param != "" and param is not None

    def filter_queryset(self, queryset):
        queryset = queryset.filter()
        print(self.cleaned_data)

        author = self.cleaned_data.get("author")
        year = self.cleaned_data.get("year")
        alphabet = self.cleaned_data.get("alphabet")

        # filter by author
        if self.is_valid_queryparam(author):
            queryset = queryset.filter(
                Q(authoring_body__name=author) | Q(court__name=author)
            )

        # filter by year
        if self.is_valid_queryparam(year):
            queryset = queryset.filter(date__year=year)

        # filter by alphabetical title
        if self.is_valid_queryparam(alphabet):
            queryset = queryset.filter(title__istartswith=alphabet)

        # all facets selected
        if (
            self.is_valid_queryparam(author)
            and self.is_valid_queryparam(year)
            and self.is_valid_queryparam(alphabet)
        ):
            queryset = queryset.filter(
                title__istartswith=alphabet,
                date__year=year,
                authoring_body__name=author,
            )

        return queryset
