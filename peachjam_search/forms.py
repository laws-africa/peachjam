from django import forms

from peachjam_search.models import SavedSearch


class SavedSearchForm(forms.ModelForm):
    class Meta:
        model = SavedSearch
        fields = ["q", "filters", "note"]
