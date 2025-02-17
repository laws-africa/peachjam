from django import forms

from peachjam_search.models import SavedSearch, SearchFeedback


class SavedSearchCreateForm(forms.ModelForm):
    class Meta:
        model = SavedSearch
        fields = ["q", "filters", "note"]


class SavedSearchUpdateForm(forms.ModelForm):
    class Meta:
        model = SavedSearch
        fields = ["note"]


class SearchFeedbackCreateForm(forms.ModelForm):
    class Meta:
        model = SearchFeedback
        fields = ["name", "email", "search_trace", "feedback"]
