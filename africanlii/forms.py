from django import forms


class BaseDocumentFilterForm(forms.Form):
    """This is the main form used for filtering Document ListViews,
    using facets such as year and alphabetical title.
    """

    alphabet = forms.CharField(required=False)
    year = forms.CharField(required=False)
    court = forms.CharField(required=False)
    author = forms.CharField(required=False)
    doc_type = forms.CharField(required=False)

    def filter_queryset(self, queryset):

        year = self.cleaned_data.get("year")
        alphabet = self.cleaned_data.get("alphabet")
        author = self.cleaned_data.get("author")
        doc_type = self.cleaned_data.get("doc_type")

        if year:
            queryset = queryset.filter(date__year=year)

        if alphabet:
            queryset = queryset.filter(title__istartswith=alphabet)

        if author:
            print(queryset)
            queryset = queryset.filter(author__name__iexact=author)

        if doc_type:
            queryset = queryset.filter(doc_type=doc_type)

        return queryset
