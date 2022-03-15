from django import forms

class DecisionFilterForm(forms.Form):
    matter_type = forms.CharField(required=False)
    date = forms.DateField(required=False)
    citation = forms.CharField(required=False)
    case_number_numeric = forms.CharField(required=False) 
    case_number_year = forms.IntegerField(required=False, min_value=0)
