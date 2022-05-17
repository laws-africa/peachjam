from africanlii.forms import BaseDocumentFilterForm


class FilteredDocumentListView(BaseDocumentFilterForm):
    """Generic List View class for filtering documents."""

    def get_queryset(self):
        self.form = BaseDocumentFilterForm(self.request.GET)
        self.form.is_valid()
        queryset = self.model.objects.all()
        return self.form.filter_queryset(queryset)
