import copy

from allauth.account.forms import LoginForm, SignupForm
from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.mail import send_mail
from django.http import QueryDict
from django.template.loader import render_to_string
from django.utils.translation import gettext as _
from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV2Invisible

from peachjam.models import (
    AttachedFiles,
    CoreDocument,
    Folder,
    SavedDocument,
    SourceFile,
    pj_settings,
)
from peachjam.plugins import plugins
from peachjam.storage import clean_filename

User = get_user_model()


def work_choices():
    return [("", "---")] + [
        (doc.work.pk, doc.title) for doc in CoreDocument.objects.order_by("title")
    ]


def adapter_choices():
    return [(key, p.name) for key, p in plugins.registry["ingestor-adapter"].items()]


class NewDocumentFormMixin:
    """Mixin for the admin view when creating a new document that adds a new field to allow the user to upload a
    file from which key data can be extracted.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["upload_file"] = forms.FileField(required=False)

    def clean_upload_file(self):
        if self.cleaned_data["upload_file"]:
            self.cleaned_data["upload_file"].name = clean_filename(
                self.cleaned_data["upload_file"].name
            )
        return self.cleaned_data["upload_file"]

    def _save_m2m(self):
        super()._save_m2m()
        if self.cleaned_data.get("upload_file"):
            self.process_upload_file(self.cleaned_data["upload_file"])
            self.run_analysis()

    def process_upload_file(self, upload_file):
        # store the uploaded file
        upload_file.seek(0)
        SourceFile(
            document=self.instance,
            file=File(upload_file, name=upload_file.name),
            filename=upload_file.name,
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


class PermissiveTypedListField(forms.TypedMultipleChoiceField):
    """Field that accepts multiple values and coerces its values to the right type, ignoring any that can't be coerced.
    Defaults to raw form data, which is strings for querystring-based forms."""

    def _coerce(self, value):
        """Validate that the values can be coerced to the right type, and ignore anything dodgy."""
        if value == self.empty_value or value in self.empty_values:
            return self.empty_value
        new_value = []
        for choice in value:
            try:
                new_value.append(self.coerce(choice))
            except (ValueError, TypeError, ValidationError):
                pass
        return new_value

    def valid_value(self, value):
        return True


def remove_nulls(value):
    return value.replace("\x00", "") if value else value


class BaseDocumentFilterForm(forms.Form):
    """This is the main form used for filtering Document ListViews,
    using facets such as year and alphabetical title.
    """

    years = PermissiveTypedListField(coerce=int, required=False)
    alphabet = forms.CharField(required=False)
    authors = PermissiveTypedListField(coerce=remove_nulls, required=False)
    doc_type = PermissiveTypedListField(coerce=remove_nulls, required=False)
    judges = PermissiveTypedListField(coerce=remove_nulls, required=False)
    natures = PermissiveTypedListField(coerce=remove_nulls, required=False)
    localities = PermissiveTypedListField(coerce=remove_nulls, required=False)
    registries = PermissiveTypedListField(coerce=remove_nulls, required=False)
    attorneys = PermissiveTypedListField(coerce=remove_nulls, required=False)
    outcomes = PermissiveTypedListField(coerce=remove_nulls, required=False)
    taxonomies = PermissiveTypedListField(coerce=remove_nulls, required=False)
    q = forms.CharField(required=False)

    sort = forms.ChoiceField(
        required=False,
        choices=[
            ("title", _("Title") + " (A - Z)"),
            ("-title", _("Title") + " (Z - A)"),
            ("-date", _("Date") + " " + _("(Newest first)")),
            ("date", _("Date") + " " + _("(Oldest first)")),
        ],
    )

    def __init__(self, defaults, data, *args, **kwargs):
        self.params = QueryDict(mutable=True)
        self.params.update({"sort": "title"})
        self.params.update(defaults or {})
        self.params.update(data)

        super().__init__(self.params, *args, **kwargs)

    def filter_queryset(self, queryset, exclude=None, filter_q=False):
        years = self.cleaned_data.get("years", [])
        alphabet = self.cleaned_data.get("alphabet")
        authors = self.cleaned_data.get("authors", [])
        courts = self.cleaned_data.get("courts", [])
        doc_type = self.cleaned_data.get("doc_type", [])
        judges = self.cleaned_data.get("judges", [])
        natures = self.cleaned_data.get("natures", [])
        localities = self.cleaned_data.get("localities", [])
        registries = self.cleaned_data.get("registries", [])
        attorneys = self.cleaned_data.get("attorneys", [])
        outcomes = self.cleaned_data.get("outcomes", [])
        taxonomies = self.cleaned_data.get("taxonomies", [])
        q = self.cleaned_data.get("q")

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
            queryset = queryset.filter(judges__name__in=judges).distinct()

        if natures and exclude != "natures":
            queryset = queryset.filter(nature__code__in=natures)

        if localities and exclude != "localities":
            queryset = queryset.filter(locality__name__in=localities)

        if registries and exclude != "registries":
            queryset = queryset.filter(registry__name__in=registries)

        if attorneys and exclude != "attorneys":
            queryset = queryset.filter(attorneys__name__in=attorneys).distinct()

        if outcomes and exclude != "outcomes":
            queryset = queryset.filter(outcomes__code__in=outcomes).distinct()

        if taxonomies and exclude != "taxonomies":
            queryset = queryset.filter(taxonomies__topic__slug__in=taxonomies)

        if filter_q and q and exclude != "q":
            queryset = queryset.filter(title__icontains=q)

        return queryset

    def order_queryset(self, queryset, exclude=None):
        sort = self.cleaned_data.get("sort") or "-date"
        queryset = queryset.order_by(sort, "title")
        return queryset


class GazetteFilterForm(BaseDocumentFilterForm):
    sub_publications = PermissiveTypedListField(coerce=remove_nulls, required=False)

    def filter_queryset(self, queryset, exclude=None, filter_q=False):
        queryset = super().filter_queryset(queryset, exclude, filter_q)

        sub_publications = self.cleaned_data.get("sub_publications", [])
        if sub_publications and exclude != "sub_publications":
            queryset = queryset.filter(sub_publication__in=sub_publications)

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
            # get the old file and make sure it's deleted
            if self.instance.pk:
                existing = self.instance.__class__.objects.get(pk=self.instance.pk)
                if existing.file:
                    existing.file.delete(False)
            self.instance.size = None
            self.instance.mimetype = None
            self.instance.filename = self.instance.file.name
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
    problem_description = forms.CharField(widget=forms.Textarea, required=True)
    problem_category = forms.CharField(widget=forms.Textarea, required=True)
    email_address = forms.EmailField(required=False)

    def send_email(self):
        document_link = self.cleaned_data["document_link"]
        problem_description = self.cleaned_data["problem_description"]
        problem_category = self.cleaned_data["problem_category"]
        email_address = self.cleaned_data["email_address"]

        context = {
            "document_link": document_link,
            "problem_description": problem_description,
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

        subject = settings.EMAIL_SUBJECT_PREFIX + _("Document problem reported")

        default_admin_emails = [email for name, email in settings.ADMINS]
        site_admin_emails = (pj_settings().admin_emails or "").split()

        send_mail(
            subject=subject,
            message=plain_txt_msg,
            from_email=None,
            recipient_list=default_admin_emails + site_admin_emails,
            html_message=html,
            fail_silently=False,
        )


class SaveDocumentForm(forms.ModelForm):
    new_folder = forms.CharField(max_length=255, required=False)

    class Meta:
        model = SavedDocument
        fields = ["document", "folder", "new_folder"]
        widgets = {"document": forms.HiddenInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["folder"].queryset = self.instance.user.folders.all()
        self.fields["document"].required = False

    def clean(self):
        cleaned_data = super().clean()
        cleaned_data["document"] = self.instance.document
        if cleaned_data.get("new_folder"):
            folder, _ = Folder.objects.get_or_create(
                name=cleaned_data["new_folder"],
                user=self.instance.user,
            )
            cleaned_data["folder"] = folder
        return cleaned_data


class PeachjamSignupForm(SignupForm):
    captcha = ReCaptchaField(widget=ReCaptchaV2Invisible)


class PeachjamLoginForm(LoginForm):
    captcha = ReCaptchaField(widget=ReCaptchaV2Invisible)
