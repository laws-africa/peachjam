import copy
from datetime import date

from ckeditor.widgets import CKEditorWidget
from django import forms
from django.conf import settings
from django.contrib import admin
from django.contrib.contenttypes.admin import GenericStackedInline
from django.http.response import FileResponse
from django.shortcuts import get_object_or_404
from django.urls import path, reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.dates import MONTHS
from django.utils.html import format_html
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from import_export.admin import ImportMixin
from languages_plus.models import Language
from treebeard.admin import TreeAdmin
from treebeard.forms import movenodeform_factory

from peachjam.forms import IngestorForm, NewDocumentFormMixin, SourceFileForm
from peachjam.models import (
    AlternativeName,
    Article,
    AttachedFileNature,
    AttachedFiles,
    Author,
    Book,
    CaseNumber,
    CitationLink,
    Court,
    CourtClass,
    CourtRegistry,
    DocumentNature,
    DocumentTopic,
    EntityProfile,
    ExternalDocument,
    Gazette,
    GenericDocument,
    Image,
    Ingestor,
    IngestorSetting,
    Journal,
    Judge,
    Judgment,
    LegalInstrument,
    Legislation,
    Locality,
    MatterType,
    PeachJamSettings,
    Predicate,
    Relationship,
    SourceFile,
    Taxonomy,
    UserProfile,
    Work,
    pj_settings,
)
from peachjam.resources import GenericDocumentResource, JudgmentResource
from peachjam.tasks import extract_citations as extract_citations_task
from peachjam_search.tasks import search_model_saved


class EntityProfileForm(forms.ModelForm):
    about_html = forms.CharField(
        widget=CKEditorWidget(),
        required=False,
    )

    class Meta:
        model = EntityProfile
        exclude = []


class EntityProfileInline(GenericStackedInline):
    model = EntityProfile
    extra = 0
    form = EntityProfileForm


class PeachJamSettingsAdmin(admin.ModelAdmin):
    filter_horizontal = (
        "document_languages",
        "document_jurisdictions",
    )


class SourceFileFilter(admin.SimpleListFilter):
    title = "by document type"
    parameter_name = "doc_type"

    def lookups(self, request, model_admin):
        return (
            ("generic", "Generic"),
            ("judgment", "Judgment"),
            ("legislation", "Legislation"),
            ("legal_instrument", "Legal Instrument"),
        )

    def queryset(self, request, queryset):
        if self.value() == "generic":
            return queryset.filter(document__doc_type="generic_document")
        elif self.value() == "judgment":
            return queryset.filter(document__doc_type="judgment")
        elif self.value() == "legislation":
            return queryset.filter(document__doc_type="legislation")
        elif self.value() == "legal_instrument":
            return queryset.filter(document__doc_type="legal_instrument")
        else:
            return queryset


class SourceFileAdmin(admin.ModelAdmin):
    list_display = ("filename",)
    list_filter = (SourceFileFilter,)
    search_fields = ("filename",)


admin.site.register(SourceFile, SourceFileAdmin)


class BaseAttachmentFileInline(admin.TabularInline):
    extra = 0
    readonly_fields = ("filename", "mimetype", "attachment_link", "size")

    def attachment_link(self, obj):
        if obj.pk:
            return format_html(
                '<a href="{url}">{title}</a>',
                url=reverse(
                    "admin:peachjam_source_file",
                    kwargs={
                        "pk": obj.pk,
                    },
                ),
                title=obj.filename,
            )


class SourceFileInline(BaseAttachmentFileInline):
    model = SourceFile
    form = SourceFileForm
    readonly_fields = (*BaseAttachmentFileInline.readonly_fields, "source_url")


class DocumentTopicInline(admin.TabularInline):
    model = DocumentTopic
    extra = 1


class AlternativeNameInline(admin.TabularInline):
    model = AlternativeName
    extra = 1


class DateSelectorWidget(forms.MultiWidget):
    def __init__(self, attrs=None):
        months = [("", "Month")] + list(MONTHS.items())
        widgets = [
            forms.NumberInput(
                attrs={
                    "placeholder": "Day",
                    "min": 1,
                    "max": 31,
                    "class": "vIntegerField mx-1",
                }
            ),
            forms.Select(attrs={"placeholder": "Month"}, choices=months),
            forms.NumberInput(
                attrs={
                    "placeholder": "Year",
                    "min": 1500,
                    "max": date.today().year,
                    "class": "vIntegerField mx-1",
                }
            ),
        ]
        super().__init__(widgets, attrs)

    def decompress(self, value):
        if isinstance(value, date):
            return [value.day, value.month, value.year]
        elif isinstance(value, str):
            year, month, day = value.split("-")
            return [day, month, year]
        return [None, None, None]

    def value_from_datadict(self, data, files, name):
        day, month, year = super().value_from_datadict(data, files, name)
        # DateField expects a single string that it can parse into a date.
        if not day and not month and not year:
            return None
        return "{}-{}-{}".format(year, month, day)


class DocumentForm(forms.ModelForm):
    content_html = forms.CharField(
        widget=CKEditorWidget(
            extra_plugins=["lawwidgets"],
            external_plugin_resources=[
                ("lawwidgets", "/static/js/ckeditor-lawwidgets/", "plugin.js")
            ],
        ),
        required=False,
    )
    flynote = forms.CharField(widget=CKEditorWidget(), required=False)
    headnote_holding = forms.CharField(widget=CKEditorWidget(), required=False)
    date = forms.DateField(widget=DateSelectorWidget())

    def __init__(self, data=None, *args, **kwargs):
        if data:
            # derive some defaults from other fields
            data = data.copy()
            if "frbr_uri_date" in self.base_fields and not data.get("frbr_uri_date"):
                try:
                    data["frbr_uri_date"] = parse_date(
                        DateSelectorWidget().value_from_datadict(data, None, "date")
                    ).strftime("%Y-%m-%d")
                except ValueError:
                    pass

        super().__init__(data, *args, **kwargs)

        # adjust form based on peach jam site settings
        settings = pj_settings()
        self.fields["language"].initial = settings.default_document_language
        if settings.document_languages.exists():
            self.fields["language"].queryset = settings.document_languages
        if settings.document_languages.exists():
            self.fields["jurisdiction"].queryset = settings.document_jurisdictions

        if "frbr_uri_doctype" in self.fields:
            # customise doctype options for different document models
            self.fields["frbr_uri_doctype"].choices = [
                (x, x) for x in self.Meta.model.frbr_uri_doctypes
            ]

        if self.instance and self.instance.content_html_is_akn:
            self.fields["content_html"].widget.attrs["readonly"] = True

    def clean_content_html(self):
        # prevent CKEditor-based editing of AKN HTML
        if self.instance.content_html_is_akn:
            return self.instance.content_html
        return self.cleaned_data["content_html"]

    def _save_m2m(self):
        super()._save_m2m()
        # update document text
        self.instance.update_text_content()


class DocumentAdmin(admin.ModelAdmin):
    form = DocumentForm
    inlines = [DocumentTopicInline, SourceFileInline, AlternativeNameInline]
    list_display = (
        "title",
        "jurisdiction",
        "locality",
        "language",
        "date",
    )
    list_filter = ("jurisdiction", "locality", "language")
    search_fields = ("title", "date")
    readonly_fields = (
        "expression_frbr_uri",
        "work",
        "created_at",
        "updated_at",
        "work_frbr_uri",
        "toc_json",
        "work_link",
    )
    exclude = ("doc_type",)
    date_hierarchy = "date"
    prepopulated_fields = {"frbr_uri_number": ("title",)}
    actions = ["extract_citations", "reextract_content", "reindex_for_search"]

    fieldsets = [
        (
            gettext_lazy("Key details"),
            {
                "fields": [
                    "work_link",
                    "jurisdiction",
                    "locality",
                    "title",
                    "date",
                    "language",
                ]
            },
        ),
        (
            gettext_lazy("Additional details"),
            {
                "fields": [
                    "citation",
                    "source_url",
                    "created_at",
                    "updated_at",
                    "expression_frbr_uri",
                ]
            },
        ),
        (
            gettext_lazy("Work identification"),
            {
                "fields": [
                    "work_frbr_uri",
                    "frbr_uri_doctype",
                    "frbr_uri_subtype",
                    "frbr_uri_actor",
                    "frbr_uri_date",
                    "frbr_uri_number",
                ],
            },
        ),
        (
            gettext_lazy("Content"),
            {
                "fields": [
                    "content_html",
                ]
            },
        ),
        (
            gettext_lazy("Advanced"),
            {
                "classes": ("collapse",),
                "fields": [
                    "toc_json",
                    "content_html_is_akn",
                    "allow_robots",
                ],
            },
        ),
    ]

    new_document_form_mixin = NewDocumentFormMixin

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.prefetch_related("locality", "jurisdiction")
        return qs

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if obj is None:
            fieldsets = self.new_document_form_mixin.adjust_fieldsets(fieldsets)
        return fieldsets

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs["fields"] = self.new_document_form_mixin.adjust_fields(
                kwargs["fields"]
            )
            form = super().get_form(request, obj, **kwargs)

            class NewForm(self.new_document_form_mixin, form):
                pass

            return NewForm

        return super().get_form(request, obj, **kwargs)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        # after saving related models, also save this model again so that it can update fields based on related changes
        form.instance.save()

    def get_urls(self):
        return [
            path(
                "source_files/<int:pk>",
                self.admin_site.admin_view(self.download_sourcefile),
                name="peachjam_source_file",
            ),
        ] + super().get_urls()

    def work_link(self, instance):
        if instance.work:
            return format_html(
                '<a href="{}">{}</a>',
                reverse("admin:peachjam_work_change", args=[instance.work.id]),
                instance.work,
            )

    work_link.short_description = "Work"

    def download_sourcefile(self, request, pk):
        source_file = get_object_or_404(SourceFile.objects, pk=pk)
        return FileResponse(source_file.file)

    def extract_citations(self, request, queryset):
        count = queryset.count()
        for doc in queryset:
            extract_citations_task(doc.pk)
        self.message_user(
            request, f"Queued tasks to extract citations from {count} documents."
        )

    extract_citations.short_description = "Extract citations (background)"

    def reextract_content(self, request, queryset):
        """Re-extract content from source files that are Word documents, overwriting content_html."""
        count = 0
        for doc in queryset:
            if doc.extract_content_from_source_file():
                count += 1
                doc.extract_citations()
                doc.save()
        self.message_user(request, f"Re-imported content from {count} documents.")

    reextract_content.short_description = "Re-extract content from DOCX files"

    def reindex_for_search(self, request, queryset):
        """Setup a background task to re-index documents for search."""
        count = queryset.count()
        for doc in queryset:
            search_model_saved(doc._meta.label, doc.pk)
        self.message_user(request, f"Queued tasks to re-index for {count} documents.")

    reindex_for_search.short_description = "Re-index for search (background)"


class TaxonomyAdmin(TreeAdmin):
    form = movenodeform_factory(Taxonomy)
    readonly_fields = ("slug",)
    inlines = [EntityProfileInline]


class GenericDocumentAdmin(ImportMixin, DocumentAdmin):
    resource_class = GenericDocumentResource
    fieldsets = copy.deepcopy(DocumentAdmin.fieldsets)
    fieldsets[0][1]["fields"].extend(["author", "nature"])

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.prefetch_related("author", "nature")
        return qs


class LegalInstrumentAdmin(ImportMixin, DocumentAdmin):
    fieldsets = copy.deepcopy(DocumentAdmin.fieldsets)
    fieldsets[0][1]["fields"].extend(["author", "nature"])

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.prefetch_related("author", "nature")
        return qs


class LegislationAdmin(ImportMixin, DocumentAdmin):
    fieldsets = copy.deepcopy(DocumentAdmin.fieldsets)
    fieldsets[0][1]["fields"].extend(["nature"])
    fieldsets[3][1]["fields"].extend(["metadata_json"])
    fieldsets[2][1]["classes"] = ("collapse",)
    fieldsets[4][1]["fields"].extend(["parent_work"])
    readonly_fields = ["parent_work"] + list(DocumentAdmin.readonly_fields)


class CaseNumberAdmin(admin.TabularInline):
    model = CaseNumber
    extra = 1
    verbose_name = gettext_lazy("case number")
    verbose_name_plural = gettext_lazy("case numbers")
    readonly_fields = ["string"]
    fields = ["matter_type", "number", "year", "string_override"]


class AttachedFilesInline(BaseAttachmentFileInline):
    model = AttachedFiles


class JudgmentAdminForm(DocumentForm):
    hearing_date = forms.DateField(widget=DateSelectorWidget(), required=False)

    class Meta:
        model = Judgment
        fields = ("hearing_date",)

    def save(self, *args, **kwargs):
        if (
            "serial_number_override" in self.changed_data
            and not self.cleaned_data["serial_number_override"]
        ):
            # if the serial number override is reset, then also clear the serial number so that it is
            # re-assigned
            self.instance.serial_number = None
        return super().save(*args, **kwargs)


class JudgmentAdmin(ImportMixin, DocumentAdmin):
    form = JudgmentAdminForm
    resource_class = JudgmentResource
    inlines = [CaseNumberAdmin, AttachedFilesInline] + DocumentAdmin.inlines
    filter_horizontal = ("judges",)
    list_filter = (*DocumentAdmin.list_filter, "court")
    fieldsets = copy.deepcopy(DocumentAdmin.fieldsets)
    fieldsets[0][1]["fields"].insert(3, "court")
    fieldsets[0][1]["fields"].insert(4, "case_name")
    fieldsets[0][1]["fields"].insert(7, "mnc")
    fieldsets[0][1]["fields"].insert(8, "serial_number_override")
    fieldsets[0][1]["fields"].insert(9, "serial_number")
    fieldsets[0][1]["fields"].append("hearing_date")
    fieldsets[1][1]["fields"].insert(0, "judges")
    fieldsets[2][1]["classes"] = ["collapse"]
    fieldsets[3][1]["fields"].extend(
        ["headnote_holding", "additional_citations", "flynote"]
    )
    readonly_fields = [
        "mnc",
        "serial_number",
        "title",
        "citation",
        "frbr_uri_doctype",
        "frbr_uri_subtype",
        "frbr_uri_actor",
        "frbr_uri_date",
        "frbr_uri_number",
    ] + list(DocumentAdmin.readonly_fields)
    prepopulated_fields = {}


@admin.register(Predicate)
class PredicateAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name", "verb")
    prepopulated_fields = {"slug": ("name",)}


class IngestorSettingInline(admin.TabularInline):
    model = IngestorSetting
    extra = 1


@admin.register(Ingestor)
class IngestorAdmin(admin.ModelAdmin):
    inlines = [IngestorSettingInline]
    readonly_fields = ("last_refreshed_at",)
    form = IngestorForm
    actions = ["refresh_all_content"]
    fields = ("adapter", "name", "last_refreshed_at", "enabled")
    list_display = ("name", "last_refreshed_at", "enabled")

    def refresh_all_content(self, request, queryset):
        from peachjam.tasks import run_ingestors

        queryset.update(last_refreshed_at=None)
        # queue up the background ingestor update task
        run_ingestors()
        self.message_user(request, _("Refreshing content in the background."))

    refresh_all_content.short_description = gettext_lazy("Refresh all content")


class ArticleForm(forms.ModelForm):
    body = forms.CharField(widget=CKEditorWidget())


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    form = ArticleForm
    list_display = ("title", "date", "published")
    list_display_links = ("title",)
    fields = (
        "title",
        "slug",
        "date",
        "published",
        "image",
        "topics",
        "summary",
        "body",
        "author",
    )
    prepopulated_fields = {"slug": ("title",)}

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields["author"].initial = request.user
        if not request.user.is_superuser:
            # limit author choices to the current user
            form.base_fields["author"].queryset = request.user.__class__.objects.filter(
                pk=request.user.pk
            )
        return form


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    pass


class RelationshipInline(admin.TabularInline):
    model = Relationship
    fk_name = "subject_work"
    fields = ("predicate", "object_work")


@admin.register(Work)
class WorkAdmin(admin.ModelAdmin):
    fields = ("title", "frbr_uri", "languages")
    search_fields = ("title", "frbr_uri")
    list_display = fields
    readonly_fields = fields
    inlines = [RelationshipInline]

    def has_add_permission(self, request):
        # disallow adding works, they are managed automatically
        return False


@admin.register(DocumentNature)
class DocumentNatureAdmin(admin.ModelAdmin):
    search_fields = ("name", "code")
    list_display = ("name", "code")
    prepopulated_fields = {"code": ("name",)}


@admin.register(Court)
class CourtAdmin(admin.ModelAdmin):
    inlines = [EntityProfileInline]


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    inlines = [EntityProfileInline]


@admin.register(Gazette)
class GazetteAdmin(DocumentAdmin):
    pass


@admin.register(Book)
class BookAdmin(DocumentAdmin):
    pass


@admin.register(Journal)
class JournalAdmin(DocumentAdmin):
    pass


@admin.register(ExternalDocument)
class ExternalDocumentAdmin(DocumentAdmin):

    prepopulated_fields = {"frbr_uri_number": ("title",)}

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields["source_url"].required = True
        form.base_fields["date"].initial = timezone.now().date()
        form.base_fields["language"].initial = Language.objects.get(iso_639_3="eng")

        return form


admin.site.register(
    [
        Image,
        Locality,
        CitationLink,
        Judge,
        MatterType,
        CourtClass,
        AttachedFileNature,
        CourtRegistry,
    ]
)
admin.site.register(PeachJamSettings, PeachJamSettingsAdmin)
admin.site.register(Taxonomy, TaxonomyAdmin)
admin.site.register(GenericDocument, GenericDocumentAdmin)
admin.site.register(Legislation, LegislationAdmin)
admin.site.register(LegalInstrument, LegalInstrumentAdmin)
admin.site.register(Judgment, JudgmentAdmin)

admin.site.site_header = settings.PEACHJAM["APP_NAME"]
