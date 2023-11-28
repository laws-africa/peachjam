import copy
from os.path import splitext

from django import forms
from django.conf import settings
from django.core.files import File
from django.core.mail import EmailMultiAlternatives
from django.http import QueryDict
from django.template.loader import render_to_string
from django.utils.text import slugify
from django.utils.translation import gettext as _

from peachjam.models import (
    AttachedFiles,
    CoreDocument,
    Ingestor,
    SourceFile,
    pj_settings,
)
from peachjam.plugins import plugins
from peachjam.storage import clean_filename


def work_choices():
    return [("", "---")] + [
        (doc.work.pk, doc.title) for doc in CoreDocument.objects.order_by("title")
    ]


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

    def _save_m2m(self):
        super()._save_m2m()
        if self.cleaned_data.get("upload_file"):
            self.process_upload_file(self.cleaned_data["upload_file"])
            self.run_analysis()

    def process_upload_file(self, upload_file):
        # store the uploaded file
        upload_file.seek(0)
        file_ext = splitext(upload_file.name)[1]
        SourceFile(
            document=self.instance,
            file=File(
                upload_file, name=f"{slugify(self.instance.title[-250:])}{file_ext}"
            ),
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

    years = forms.CharField(required=False)
    alphabet = forms.CharField(required=False)
    authors = forms.CharField(required=False)
    doc_type = forms.CharField(required=False)
    judges = forms.CharField(required=False)
    natures = forms.CharField(required=False)
    localities = forms.CharField(required=False)
    registries = forms.CharField(required=False)
    attorneys = forms.CharField(required=False)
    order_outcomes = forms.CharField(required=False)

    def __init__(self, data, *args, **kwargs):
        self.params = QueryDict(mutable=True)
        self.params.update(data)

        super().__init__(self.params, *args, **kwargs)

    def filter_queryset(self, queryset, exclude=None):
        years = self.params.getlist("years")
        alphabet = self.cleaned_data.get("alphabet")
        authors = self.params.getlist("authors")
        courts = self.params.getlist("courts")
        doc_type = self.params.getlist("doc_type")
        judges = self.params.getlist("judges")
        natures = self.params.getlist("natures")
        localities = self.params.getlist("localities")
        registries = self.params.getlist("registries")
        attorneys = self.params.getlist("attorneys")
        order_outcomes = self.params.getlist("order_outcomes")

        queryset = self.order_queryset(queryset, exclude)

        if years and exclude != "years":
            queryset = queryset.filter(date__year__in=years)

        if alphabet and exclude != "alphabet":
            queryset = queryset.filter(title__istartswith=alphabet)

        if authors and exclude != "authors":
            queryset = queryset.filter(authors__name__in=authors)

        if courts and exclude != "courts":
            queryset = queryset.filter(court__name__in=courts)

        if doc_type and exclude != "doc_type":
            queryset = queryset.filter(doc_type__in=doc_type)

        if judges and exclude != "judges":
            queryset = queryset.filter(judges__name__in=judges)

        if natures and exclude != "natures":
            queryset = queryset.filter(nature__name__in=natures)

        if localities and exclude != "localities":
            queryset = queryset.filter(locality__name__in=localities)

        if registries and exclude != "registries":
            queryset = queryset.filter(registry__name__in=registries)

        if attorneys and exclude != "attorneys":
            queryset = queryset.filter(attorneys__name__in=attorneys)

        if order_outcomes and exclude != "order_outcomes":
            queryset = queryset.filter(order_outcome__name__in=order_outcomes)

        return queryset

    def order_queryset(self, queryset, exclude=None):
        if self.cleaned_data.get("alphabet") and exclude != "alphabet":
            queryset = queryset.order_by("title")
        else:
            queryset = queryset.order_by("-date", "title")
        return queryset


class AttachmentFormMixin:
    """Admin form for editing models that extend from AbstractAttachmentModel."""

    def clean_file(self):
        # dynamic storage files don't like colons in filenames
        self.cleaned_data["file"].name = clean_filename(self.cleaned_data["file"].name)
        return self.cleaned_data["file"]

    def save(self, commit=True):
        # clear these for changed files so they get updated
        if "file" in self.changed_data:
            self.instance.size = None
            self.instance.mimetype = None
        return super().save(commit)


class SourceFileForm(AttachmentFormMixin, forms.ModelForm):
    class Meta:
        model = SourceFile
        fields = "__all__"
        exclude = ("file_as_pdf",)

    def _save_m2m(self):
        super()._save_m2m()
        if "file" in self.changed_data:
            if self.instance.document.extract_content_from_source_file():
                self.instance.document.save()

                # if the file is changed, we need delete the existing pdf and re-generate
                self.instance.file_as_pdf.delete()
                self.instance.ensure_file_as_pdf()


class AttachedFilesForm(AttachmentFormMixin, forms.ModelForm):
    class Meta:
        model = AttachedFiles
        fields = "__all__"


class DocumentProblemForm(forms.Form):
    document_link = forms.CharField(max_length=255, required=True)
    problem_description = forms.CharField(widget=forms.Textarea, required=False)
    other_problem_description = forms.CharField(widget=forms.Textarea, required=False)
    problem_category = forms.CharField(required=True)
    email_address = forms.EmailField(required=True)

    def send_email(self):
        document_link = self.cleaned_data["document_link"]
        problem_description = self.cleaned_data.get("problem_description")
        other_problem_description = self.cleaned_data.get("other_problem_description")
        problem_category = self.cleaned_data["problem_category"]
        email_address = self.cleaned_data["email_address"]

        context = {
            "document_link": document_link,
            "problem_description": problem_description,
            "other_problem_description": other_problem_description,
            "problem_category": problem_category,
        }
        if email_address:
            context["email_address"] = email_address

        html = render_to_string(
            "peachjam/emails/document_problem_email.html", context=context
        )
        plain_txt_msg = render_to_string(
            "peachjam/emails/document_problem_email.txt",
            context=context,
        )

        subject = _("Document problem reported on %(app_name)s") % {
            "app_name": settings.PEACHJAM["APP_NAME"]
        }

        # get admin emails from settings
        admin_emails = [admin[1] for admin in settings.ADMINS]

        # get admin emails from site settings
        site_admin_emails = list(
            pj_settings().admin_emails.values_list("email", flat=True)
        )

        recipients = admin_emails + site_admin_emails

        email = EmailMultiAlternatives(
            subject=subject,
            body=plain_txt_msg,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipients,
        )
        email.attach_alternative(html, "text/html")
        email.send(fail_silently=True)
