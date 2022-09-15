from django import forms

from peachjam.forms import BaseDocumentFilterForm


class CourtViewFilterForm(BaseDocumentFilterForm):
    judge = forms.CharField(required=False)

    def filter_queryset(self, queryset, exclude=None):
        queryset = super().filter_queryset(queryset, exclude)

        judge = self.params.getlist("judge")
        if judge and exclude != "judge":
            queryset = queryset.filter(judges__name__in=judge)

        return queryset
