from django import forms

from peachjam.models import CoreDocument, Relationship


def work_choices():
    return [("", "---")] + [
        (work_frbr_uri, title)
        for title, work_frbr_uri in CoreDocument.objects.values_list(
            "title", "work_frbr_uri"
        )
        .order_by("title")
        .distinct()
    ]


class RelationshipForm(forms.ModelForm):
    object_work_frbr_uri = forms.ChoiceField(choices=work_choices)

    class Meta:
        model = Relationship
        fields = ["predicate", "object_work_frbr_uri"]

    def __init__(self, subject_doc, *args, **kwargs):
        self.subject_doc = subject_doc
        super().__init__(*args, **kwargs)
