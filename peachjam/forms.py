import copy
from os.path import splitext

from django import forms
from django.core.files import File
from django.http import QueryDict

from peachjam.models import CoreDocument, Ingestor, Relationship, SourceFile, Work
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


class NewDocumentFormMixin:
    """Mixin for the admin view when creating a new document that adds a new field to allow the user to upload a
    file from which key data can be extracted.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["upload_file"] = forms.FileField(required=False)

    def save(self, commit=True):
        obj = super().save(commit)
        if self.cleaned_data.get("upload_file"):
            self.process_upload_file(self.cleaned_data["upload_file"])
            self.run_analysis()
        return obj

    def process_upload_file(self, upload_file):
        # store the uploaded file
        self.instance.save()
        upload_file.seek(0)
        file_ext = splitext(upload_file.name)[1]
        SourceFile(
            document=self.instance,
            file=File(upload_file, name=f"{self.instance.title[-250:]}{file_ext}"),
            mimetype=upload_file.content_type,
        ).save()

        # extract content, if we can
        if self.instance.extract_content_from_source_file():
            self.instance.save()

    def run_analysis(self):
        """Apply analysis pipelines for this newly created document."""
        if self.instance.extract_citations():
            self.instance.save()

    @classmethod
    def adjust_fieldsets(cls, fieldsets):
        # add the upload_file to the first set of fields to include on the page
        fieldsets = copy.deepcopy(fieldsets)
        fieldsets[0][1]["fields"].append("upload_file")
        return fieldsets

    @classmethod
    def adjust_fields(cls, fields):
        # don't include 'upload_field' when generating the form
        return [f for f in fields if f != "upload_file"]


class BaseDocumentFilterForm(forms.Form):
    """This is the main form used for filtering Document ListViews,
    using facets such as year and alphabetical title.
    """

    year = forms.CharField(required=False)
    alphabet = forms.CharField(required=False)
    author = forms.CharField(required=False)
    doc_type = forms.CharField(required=False)

    def __init__(self, data, *args, **kwargs):
        self.params = QueryDict(mutable=True)
        self.params.update(data)

        super().__init__(self.params, *args, **kwargs)

    def filter_queryset(self, queryset, exclude=None):

        year = self.params.getlist("year")
        alphabet = self.cleaned_data.get("alphabet")
        author = self.params.getlist("author")
        doc_type = self.params.getlist("doc_type")

        if year and exclude != "year":
            queryset = queryset.filter(date__year__in=year)

        if alphabet and exclude != "alphabet":
            queryset = queryset.filter(title__istartswith=alphabet)

        if author and exclude != "author":
            queryset = queryset.filter(author__name__in=author)

        if doc_type and exclude != "doc_type":
            queryset = queryset.filter(doc_type__in=doc_type)

        return queryset
