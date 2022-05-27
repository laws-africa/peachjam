from django import forms


class BaseDocumentFilterForm(forms.Form):
    """This is the main form used for filtering Document ListViews,
    using facets such as year and alphabetical title.
    """

    alphabet = forms.CharField(required=False)
    year = forms.CharField(required=False)
    court = forms.CharField(required=False)
    authoring_body = forms.CharField(required=False)

    def filter_queryset(self, queryset):

        year = self.cleaned_data.get("year")
        alphabet = self.cleaned_data.get("alphabet")
        court = self.cleaned_data.get("court")
        authoring_body = self.cleaned_data.get("authoring_body")

        if year:
            queryset = queryset.filter(date__year=year)

        if alphabet:
            queryset = queryset.filter(title__istartswith=alphabet)

        if court:
            queryset = queryset.filter(name=court)

        if authoring_body:
            queryset = queryset.filter(name=authoring_body)

        return queryset
