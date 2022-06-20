from django import forms

from peachjam.models import CoreDocument, Relationship, Work


def work_choices():
    return [("", "---")] + [
        (doc.work.pk, doc.title) for doc in CoreDocument.objects.order_by("title")
    ]


class RelationshipForm(forms.ModelForm):
    object_work = forms.ChoiceField(choices=work_choices)

    class Meta:
        model = Relationship
        fields = ["predicate", "object_work"]

    def __init__(self, subject_work, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.subject_work = subject_work

    def clean_object_work(self):
        return Work.objects.get(pk=self.cleaned_data["object_work"])
