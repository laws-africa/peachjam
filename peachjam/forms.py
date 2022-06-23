from django import forms

from peachjam.models import CoreDocument, Ingestor, Relationship, Work
from peachjam.plugins import plugins


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


def adapter_choices():
    return [(key, p.name) for key, p in plugins.registry["ingestor-adapter"].items()]


class IngestorForm(forms.ModelForm):
    adapter = forms.ChoiceField(choices=adapter_choices)
    last_refreshed_at = forms.DateTimeField(required=False)
    name = forms.CharField(max_length=255)

    class Meta:
        model = Ingestor
        fields = ("adapter", "name")
