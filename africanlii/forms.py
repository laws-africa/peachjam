from django import forms
from django.http import QueryDict


class BaseDocumentFilterForm(forms.Form):
    """This is the main form used for filtering Document ListViews,
    using facets such as year and alphabetical title.
    """

    year = forms.CharField(required=False)
    alphabet = forms.CharField(required=False)
    author = forms.CharField(required=False)
    doc_type = forms.CharField(required=False)

    def __init__(self, data, *args, **kwargs):
        self.params = QueryDict(mutable=True)
        self.params.update(data)
        print(data)

        super().__init__(self.params, *args, **kwargs)

    def filter_queryset(self, queryset, exclude=None):

        year = self.params.getlist("year")
        alphabet = self.cleaned_data.get("alphabet")
        author = self.params.getlist("author")
        doc_type = self.params.getlist("doc_type")

        if year and exclude != "year":
            queryset = queryset.filter(date__year__in=year)

        if alphabet and exclude != "alphabet":
            queryset = queryset.filter(title__istartswith=alphabet)

        if author and exclude != "author":
            queryset = queryset.filter(author__name__in=author)

        if doc_type and exclude != "doc_type":
            queryset = queryset.filter(doc_type__in=doc_type)

        return queryset
