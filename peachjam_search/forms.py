from django import forms

from peachjam_search.models import SavedSearch


class SavedSearchCreateForm(forms.ModelForm):
    class Meta:
        model = SavedSearch
        fields = ["q", "filters", "note"]


class SavedSearchUpdateForm(forms.ModelForm):
    class Meta:
        model = SavedSearch
        fields = ["note"]
