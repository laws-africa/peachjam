import copy
import logging

from allauth.account.forms import LoginForm, SignupForm
from dal import autocomplete
from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.mail import send_mail
from django.core.mail.message import EmailMultiAlternatives
from django.db.models import Q
from django.db.models.functions.text import Substr
from django.http import QueryDict
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _
from django.utils.translation.trans_real import get_languages
from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV2Invisible
from languages_plus.models import Language

from peachjam.models import (
    Annotation,
    AttachedFiles,
    CoreDocument,
    Folder,
    PublicationFile,
    Ratification,
    SavedDocument,
    SourceFile,
    UnconstitutionalProvision,
    pj_settings,
)
from peachjam.plugins import plugins
from peachjam.storage import clean_filename

log = logging.getLogger(__name__)

User = get_user_model()


def get_recaptcha_field():
    """Return a captcha field that is disabled when running in DEBUG mode."""

    if settings.DEBUG:
        return forms.BooleanField(
            required=False,
            widget=forms.HiddenInput,
            initial=True,
        )

    return ReCaptchaField(widget=ReCaptchaV2Invisible)


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
        fieldsets[0][1]["fields"].insert(0, "upload_file")
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
    divisions = PermissiveTypedListField(coerce=remove_nulls, required=False)
    attorneys = PermissiveTypedListField(coerce=remove_nulls, required=False)
    outcomes = PermissiveTypedListField(coerce=remove_nulls, required=False)
    case_actions = PermissiveTypedListField(coerce=remove_nulls, required=False)
    taxonomies = PermissiveTypedListField(coerce=remove_nulls, required=False)
    labels = PermissiveTypedListField(coerce=remove_nulls, required=False)
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

    # fields for which filters are applied
    filter_fields = [
        "years",
        "alphabet",
        "authors",
        "courts",
        "doc_type",
        "judges",
        "natures",
        "localities",
        "registries",
        "divisions",
        "attorneys",
        "outcomes",
        "case_actions",
        "labels",
        "taxonomies",
    ]

    def __init__(self, defaults, data, *args, **kwargs):
        self.secondary_sort = "title"
        if defaults is not None:
            self.secondary_sort = defaults.get("secondary_sort", "title")
        self.params = QueryDict(mutable=True)
        self.params.update({"sort": "-date"})
        self.params.update(defaults or {})
        self.params.update(data)

        super().__init__(self.params, *args, **kwargs)

    def filter_queryset(self, queryset, exclude=None, filter_q=False):
        queryset = self.order_queryset(queryset, exclude)

        for field in self.filter_fields:
            if exclude != field:
                queryset = getattr(self, f"apply_filter_{field}")(queryset)

        if filter_q and exclude != "q":
            queryset = self.apply_filter_q(queryset)

        return queryset

    def order_queryset(self, queryset, exclude=None):
        sort = self.cleaned_data.get("sort") or "-date"
        if sort == "-date" and "frbr_uri_number" in self.secondary_sort:
            self.secondary_sort = "-frbr_uri_number"
        elif sort == "date" and "frbr_uri_number" in self.secondary_sort:
            self.secondary_sort = "frbr_uri_number"
        queryset = queryset.order_by(sort, self.secondary_sort)
        return queryset

    def apply_filter_years(self, queryset):
        years = self.cleaned_data.get("years", [])
        return queryset.filter(date__year__in=years) if years else queryset

    def apply_filter_alphabet(self, queryset):
        alphabet = self.cleaned_data.get("alphabet")
        return queryset.filter(title__istartswith=alphabet) if alphabet else queryset

    def apply_filter_authors(self, queryset):
        authors = self.cleaned_data.get("authors")
        if authors and hasattr(queryset.model, "author"):
            return queryset.filter(author__name__in=authors)
        if authors and hasattr(queryset.model, "authors"):
            return queryset.filter(authors__name__in=authors).distinct()
        return queryset

    def apply_filter_courts(self, queryset):
        courts = self.cleaned_data.get("courts", [])
        return (
            queryset.filter(court__name__in=courts)
            if courts and hasattr(queryset.model, "court")
            else queryset
        )

    def apply_filter_doc_type(self, queryset):
        doc_type = self.cleaned_data.get("doc_type", [])
        return queryset.filter(doc_type__in=doc_type) if doc_type else queryset

    def apply_filter_judges(self, queryset):
        judges = self.cleaned_data.get("judges", [])
        return (
            queryset.filter(judges__name__in=judges).distinct()
            if judges and hasattr(queryset.model, "judges")
            else queryset
        )

    def apply_filter_natures(self, queryset):
        natures = self.cleaned_data.get("natures", [])
        return queryset.filter(nature__code__in=natures) if natures else queryset

    def apply_filter_localities(self, queryset):
        localities = self.cleaned_data.get("localities", [])
        return (
            queryset.filter(locality__name__in=localities) if localities else queryset
        )

    def apply_filter_registries(self, queryset):
        registries = self.cleaned_data.get("registries", [])
        return (
            queryset.filter(registry__name__in=registries)
            if registries and hasattr(queryset.model, "registry")
            else queryset
        )

    def apply_filter_divisions(self, queryset):
        divisions = self.cleaned_data.get("divisions", [])
        return (
            queryset.filter(division__code__in=divisions)
            if divisions and hasattr(queryset.model, "division")
            else queryset
        )

    def apply_filter_attorneys(self, queryset):
        attorneys = self.cleaned_data.get("attorneys", [])
        return (
            queryset.filter(attorneys__name__in=attorneys).distinct()
            if attorneys and hasattr(queryset.model, "attorneys")
            else queryset
        )

    def apply_filter_outcomes(self, queryset):
        outcomes = self.cleaned_data.get("outcomes", [])
        return (
            queryset.filter(outcomes__name__in=outcomes).distinct()
            if outcomes and hasattr(queryset.model, "outcomes")
            else queryset
        )

    def apply_filter_case_actions(self, queryset):
        actions = self.cleaned_data.get("case_actions", [])
        return (
            queryset.filter(case_action__name__in=actions).distinct()
            if actions and hasattr(queryset.model, "case_action")
            else queryset
        )

    def apply_filter_labels(self, queryset):
        labels = self.cleaned_data.get("labels", [])
        return (
            queryset.filter(labels__name__in=labels).distinct() if labels else queryset
        )

    def apply_filter_taxonomies(self, queryset):
        taxonomies = self.cleaned_data.get("taxonomies", [])
        return (
            queryset.filter(taxonomies__topic__slug__in=taxonomies)
            if taxonomies
            else queryset
        )

    def apply_filter_q(self, queryset):
        q = self.cleaned_data.get("q")
        if q:
            terms = q.split()
            queries = Q()
            for term in terms:
                queries &= Q(Q(title__icontains=term) | Q(citation__icontains=term))
            queryset = queryset.filter(queries)
        return queryset


class JournalArticleFilterForm(BaseDocumentFilterForm):
    journals = PermissiveTypedListField(coerce=int, required=False)

    filter_fields = BaseDocumentFilterForm.filter_fields + ["journals"]

    def apply_filter_journals(self, queryset):
        journals = self.cleaned_data.get("journals")
        return queryset.filter(journal_id__in=journals) if journals else queryset


class LegislationFilterForm(BaseDocumentFilterForm):
    def apply_filter_years(self, queryset):
        years = self.cleaned_data.get("years", [])
        return (
            (
                queryset.annotate(
                    frbr_uri_date_year=Substr("frbr_uri_date", 1, 4)
                ).filter(frbr_uri_date_year__in=years)
            )
            if years
            else queryset
        )

    def order_queryset(self, queryset, exclude=None):
        queryset = super().order_queryset(queryset, exclude)

        # change ordering so that date uses frbr_uri_date
        ordering = list(queryset.query.order_by)
        for i, order in enumerate(ordering):
            if order == "date":
                ordering[i] = "frbr_uri_date"
            if order == "-date":
                ordering[i] = "-frbr_uri_date"

        return queryset.order_by(*ordering)


class GazetteFilterForm(BaseDocumentFilterForm):
    sub_publications = PermissiveTypedListField(coerce=remove_nulls, required=False)
    special = PermissiveTypedListField(coerce=remove_nulls, required=False)
    supplement = forms.BooleanField(required=False)

    def filter_queryset(self, queryset, exclude=None, filter_q=False):
        queryset = super().filter_queryset(queryset, exclude, filter_q)
        sub_publications = self.cleaned_data.get("sub_publications", [])
        special = self.cleaned_data.get("special", [])
        supplement = self.cleaned_data.get("supplement", False)

        if sub_publications and exclude != "sub_publications":
            queryset = queryset.filter(sub_publication__in=sub_publications)

        if special and exclude != "special":
            special_qs = Q()
            if "special" in special:
                special_qs |= Q(special=True)
            if "not_special" in special:
                special_qs |= Q(special=False)
            queryset = queryset.filter(special_qs)

        if supplement and exclude != "supplement":
            queryset = queryset.filter(supplement=True)

        return queryset


class UnconstitutionalProvisionFilterForm(BaseDocumentFilterForm):
    resolved = PermissiveTypedListField(coerce=remove_nulls, required=False)

    filter_fields = BaseDocumentFilterForm.filter_fields + ["resolved"]

    def apply_filter_resolved(self, queryset):
        resolved = self.cleaned_data.get("resolved", [])

        q = Q()
        if "resolved" in resolved:
            q |= Q(
                work__enrichments__in=UnconstitutionalProvision.objects.filter(
                    resolved=True
                )
            )
        if "unresolved" in resolved:
            q |= Q(
                work__enrichments__in=UnconstitutionalProvision.objects.filter(
                    resolved=False
                )
            )
        queryset = queryset.filter(q).distinct()
        return queryset


class AttachmentFormMixin:
    """Admin form for editing models that extend from AbstractAttachmentModel."""

    def clean_file(self):
        if self.cleaned_data["file"]:
            # dynamic storage files don't like colons in filenames
            self.cleaned_data["file"].name = clean_filename(
                self.cleaned_data["file"].name
            )
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


class PublicationFileForm(AttachmentFormMixin, forms.ModelForm):
    class Meta:
        model = PublicationFile
        fields = "__all__"


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
        recipients = site_admin_emails or default_admin_emails
        reply_to = (
            [self.cleaned_data.get("email_address")]
            if self.cleaned_data.get("email_address")
            else []
        )

        # use this sending mechanism because we can set reply-to
        mail = EmailMultiAlternatives(
            subject=subject,
            body=plain_txt_msg,
            to=recipients,
            reply_to=reply_to,
        )
        mail.attach_alternative(html, "text/html")
        mail.send(fail_silently=False)


class ContactUsForm(forms.Form):
    name = forms.CharField(max_length=255, required=True)
    email = forms.EmailField(required=True)
    message = forms.CharField(widget=forms.Textarea, required=True)
    captcha = get_recaptcha_field()

    def send_email(self):
        name = self.cleaned_data["name"]
        email = self.cleaned_data["email"]
        message = self.cleaned_data["message"]

        context = {
            "name": name,
            "email": email,
            "message": message,
            "APP_NAME": settings.PEACHJAM["APP_NAME"],
        }

        html = render_to_string(
            "peachjam/emails/contact_us_email.html", context=context
        )
        plain_txt_msg = render_to_string(
            "peachjam/emails/contact_us_email.txt",
            context=context,
        )

        subject = settings.EMAIL_SUBJECT_PREFIX + _("Contact us message")

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
    new_folder = forms.CharField(max_length=100, required=False)
    folders = forms.ModelMultipleChoiceField(
        label=_("Folders"),
        queryset=Folder.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = SavedDocument
        fields = ["folders", "new_folder", "note"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["folders"].queryset = self.instance.user.folders.all()

    def clean(self):
        cleaned_data = super().clean()
        folders = list(cleaned_data.get("folders") or [])

        if cleaned_data.get("new_folder"):
            folder, _ = Folder.objects.get_or_create(
                name=cleaned_data["new_folder"],
                user=self.instance.user,
            )
            folders.append(folder)

        if not folders:
            # default a folder
            most_recent_saved = self.instance.user.saved_documents.order_by(
                "-created_at"
            ).first()
            if most_recent_saved and most_recent_saved.folders.all().last():
                folders = [most_recent_saved.folders.all().last()]

            if not folders:
                folders = self.instance.user.folders.all()[:1]

            if not folders:
                folders = [
                    Folder.objects.get_or_create(
                        name="My Documents", user=self.instance.user
                    )[0]
                ]

        cleaned_data["folders"] = folders
        return cleaned_data


def no_links(value):
    if value and ("https:" in value) or ("http:" in value):
        raise ValidationError(_("Please provide a valid name"))


class PeachjamSignupForm(SignupForm):
    captcha = get_recaptcha_field()
    first_name = forms.CharField(
        max_length=40, label=_("First name"), required=False, validators=[no_links]
    )
    last_name = forms.CharField(
        max_length=40, label=_("Last name"), required=False, validators=[no_links]
    )


class PeachjamLoginForm(LoginForm):
    captcha = get_recaptcha_field()


class UserProfileForm(forms.Form):
    first_name = forms.CharField(max_length=255, required=False)
    last_name = forms.CharField(max_length=255, required=False)
    preferred_language = forms.ModelChoiceField(
        queryset=Language.objects.filter(iso_639_1__in=get_languages())
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        kwargs["initial"] = {
            "first_name": self.user.first_name,
            "last_name": self.user.last_name,
            "preferred_language": self.user.userprofile.preferred_language,
        }
        super().__init__(*args, **kwargs)

    def save(self):
        self.user.first_name = self.cleaned_data["first_name"]
        self.user.last_name = self.cleaned_data["last_name"]
        self.user.userprofile.preferred_language = self.cleaned_data[
            "preferred_language"
        ]
        self.user.userprofile.save()
        self.user.save()
        self.user.refresh_from_db()
        return self.user


class TermsAcceptanceForm(forms.Form):
    accepted_terms = forms.BooleanField(
        label=_("I agree to the Terms of Use"),
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        error_messages={
            "required": _("You must accept the terms to continue."),
        },
    )


class RatificationForm(forms.ModelForm):
    class Meta:
        model = Ratification
        fields = "__all__"
        widgets = {"work": autocomplete.ModelSelect2(url="autocomplete-works")}


class AnnotationForm(forms.ModelForm):
    class Meta:
        model = Annotation
        fields = ["text"]


class GuardianGroupForm(forms.Form):
    group = forms.ModelChoiceField(queryset=Group.objects.all())


class GuardianUserForm(forms.Form):
    user = forms.ModelChoiceField(queryset=User.objects.all())
