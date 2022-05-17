from django import forms


class BaseDocumentFilterForm(forms.Form):
    """This is the main form used for filtering Document ListViews,
    using facets such as year and alphabetical title.
    """

    alphabet = forms.CharField(required=False)
    year = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def is_valid_queryparam(self, param):
        return param != "" and param is not None

    def filter_queryset(self, queryset):

        year = self.cleaned_data.get("year")
        alphabet = self.cleaned_data.get("alphabet")

        # filter by year
        if self.is_valid_queryparam(year):
            queryset = queryset.filter(date__year=year)

        # filter by alphabetical title
        if self.is_valid_queryparam(alphabet):
            queryset = queryset.filter(title__istartswith=alphabet)

        return queryset
