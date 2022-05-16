from django import forms


class DocumentFilterForm(forms.Form):
    """This is the main form used for filtering Document ListViews, using facets such as year,
    author and alphabetical title.
    """

    author = forms.CharField(required=False)
    alphabet = forms.CharField(required=False)
    year = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def is_valid_queryparam(self, param):
        return param != "" and param is not None

    def filter_queryset(self, queryset):
        queryset = queryset.filter()

        author = self.cleaned_data.get("author")
        year = self.cleaned_data.get("year")
        alphabet = self.cleaned_data.get("alphabet")

        if self.is_valid_queryparam(author):
            # Take item from the queryset to determine fields to lookup with
            item = queryset[0]
            # Authors of Judgments are courts.
            # Therefore, check if court_id db column is present and use it to lookup
            if "court_id" in item.__dict__.keys():
                queryset = queryset.filter(court__name=author)

            # Models inheriting from CoreDocument have authoring_body i.e.
            # authoring_body_id db column. Hence, use authoring_body__name to lookup
            elif "authoring_body_id" in item.__dict__.keys():
                queryset = queryset.filter(authoring_body__name=author)

        # filter by year
        if self.is_valid_queryparam(year):
            queryset = queryset.filter(date__year=year)

        # filter by alphabetical title
        if self.is_valid_queryparam(alphabet):
            queryset = queryset.filter(title__istartswith=alphabet)

        return queryset
