import copy

from ckeditor.widgets import CKEditorWidget
from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin.utils import unquote
from django.http.response import FileResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.text import capfirst
from django.utils.translation import gettext_lazy as __
from import_export.admin import ImportMixin
from treebeard.admin import TreeAdmin
from treebeard.forms import movenodeform_factory

from peachjam.forms import IngestorForm, NewDocumentFormMixin, RelationshipForm
from peachjam.models import (
    Article,
    Author,
    CaseNumber,
    CitationLink,
    DocumentNature,
    DocumentTopic,
    GenericDocument,
    Image,
    Ingestor,
    IngestorSetting,
    Judge,
    Judgment,
    JudgmentMediaSummaryFile,
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
    pj_settings,
)
from peachjam.resources import GenericDocumentResource, JudgmentResource


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


class DocumentTopicInline(admin.TabularInline):
    model = DocumentTopic
    extra = 1


class DocumentForm(forms.ModelForm):
    content_html = forms.CharField(widget=CKEditorWidget(), required=False)
    flynote = forms.CharField(widget=CKEditorWidget(), required=False)
    headnote_holding = forms.CharField(widget=CKEditorWidget(), required=False)
    date = forms.DateField(widget=forms.SelectDateWidget())

    def __init__(self, data=None, *args, **kwargs):
        if data:
            # derive some defaults from other fields
            data = data.copy()
            if "frbr_uri_date" in self.base_fields and not data.get("frbr_uri_date"):
                data["frbr_uri_date"] = data.get("date")

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


class DocumentAdmin(admin.ModelAdmin):
    form = DocumentForm
    inlines = [DocumentTopicInline, SourceFileInline]
    list_display = ("title", "date")
    search_fields = ("title", "date")
    readonly_fields = (
        "expression_frbr_uri",
        "work",
        "created_at",
        "updated_at",
        "work_frbr_uri",
        "toc_json",
    )
    exclude = ("doc_type",)
    date_hierarchy = "date"
    prepopulated_fields = {"frbr_uri_number": ("title",)}
    actions = ["extract_citations", "reextract_content"]

    fieldsets = [
        (
            __("Key details"),
            {
                "fields": [
                    "jurisdiction",
                    "locality",
                    "title",
                    "date",
                    "language",
                ]
            },
        ),
        (
            __("Additional details"),
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
            "Work identification",
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
            __("Content"),
            {
                "fields": [
                    "content_html",
                ]
            },
        ),
        (
            __("Advanced"),
            {
                "classes": ("collapse",),
                "fields": [
                    "toc_json",
                    "content_html_is_akn",
                ],
            },
        ),
    ]

    new_document_form_mixin = NewDocumentFormMixin

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
        info = self.model._meta.app_label, self.model._meta.model_name

        return [
            path(
                "source_files/<int:pk>",
                self.admin_site.admin_view(self.download_sourcefile),
                name="peachjam_source_file",
            ),
            path(
                "<path:object_id>/relationships/",
                self.admin_site.admin_view(self.relationships),
                name="%s_%s_relationships" % info,
            ),
            path(
                "<path:object_id>/relationships/<path:rel_id>/delete",
                self.admin_site.admin_view(self.delete_relationship),
                name="%s_%s_delete_relationship" % info,
            ),
        ] + super().get_urls()

    def download_sourcefile(self, request, pk):
        source_file = get_object_or_404(SourceFile.objects, pk=pk)
        return FileResponse(source_file.file)

    def relationships(self, request, object_id):
        model = self.model
        obj = self.get_object(request, unquote(object_id))
        if obj is None:
            return self._get_obj_does_not_exist_redirect(
                request, model._meta, object_id
            )

        form = RelationshipForm(obj.work, request.POST)
        if request.method == "POST":
            if form.is_valid():
                form.save()
                form = RelationshipForm(obj.work)

        opts = model._meta
        context = {
            **self.admin_site.each_context(request),
            "title": "Relationships",
            "subtitle": obj,
            "module_name": str(capfirst(opts.verbose_name_plural)),
            "object": obj,
            "opts": opts,
            "preserved_filters": self.get_preserved_filters(request),
            "relationships": Relationship.for_subject_document(obj).all(),
            "form": form,
        }
        request.current_app = self.admin_site.name

        return TemplateResponse(
            request, "admin/peachjam_document_relationships.html", context
        )

    def delete_relationship(self, request, object_id, rel_id):
        rel = get_object_or_404(Relationship.objects, pk=rel_id)
        messages.success(request, f"{rel} deleted.")
        rel.delete()
        info = self.model._meta.app_label, self.model._meta.model_name
        return redirect("admin:%s_%s_relationships" % info, object_id=object_id)

    def extract_citations(self, request, queryset):
        count = 0
        for doc in queryset:
            count += 1
            if doc.extract_citations():
                doc.save()
        self.message_user(request, f"Extracted citations from {count} documents.")

    extract_citations.short_description = "Extract citations"

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


class TaxonomyAdmin(TreeAdmin):
    form = movenodeform_factory(Taxonomy)
    readonly_fields = ("slug",)


class GenericDocumentAdmin(ImportMixin, DocumentAdmin):
    resource_class = GenericDocumentResource
    fieldsets = copy.deepcopy(DocumentAdmin.fieldsets)
    fieldsets[0][1]["fields"].extend(["author", "nature"])


class LegalInstrumentAdmin(ImportMixin, DocumentAdmin):
    fieldsets = copy.deepcopy(DocumentAdmin.fieldsets)
    fieldsets[0][1]["fields"].extend(["author", "nature"])


class LegislationAdmin(ImportMixin, DocumentAdmin):
    fieldsets = copy.deepcopy(DocumentAdmin.fieldsets)
    fieldsets[3][1]["fields"].extend(["metadata_json"])
    fieldsets[2][1]["classes"] = ("collapse",)
    fieldsets[4][1]["fields"].extend(["parent_work"])
    readonly_fields = ["parent_work"] + list(DocumentAdmin.readonly_fields)


class CaseNumberAdmin(admin.TabularInline):
    model = CaseNumber
    extra = 1
    verbose_name = "Case number"
    verbose_name_plural = "Case numbers"
    readonly_fields = ["string"]
    fields = ["matter_type", "number", "year", "string_override"]


class JudgmentMediaSummaryFileInline(BaseAttachmentFileInline):
    model = JudgmentMediaSummaryFile


class JudgmentAdmin(ImportMixin, DocumentAdmin):
    resource_class = JudgmentResource
    inlines = [CaseNumberAdmin, JudgmentMediaSummaryFileInline] + DocumentAdmin.inlines
    filter_horizontal = ("judges",)
    fieldsets = copy.deepcopy(DocumentAdmin.fieldsets)
    fieldsets[0][1]["fields"].insert(3, "author")
    fieldsets[0][1]["fields"].insert(4, "case_name")
    fieldsets[0][1]["fields"].insert(7, "mnc")
    fieldsets[1][1]["fields"].insert(0, "judges")
    fieldsets[2][1]["classes"] = ["collapse"]
    fieldsets[3][1]["fields"].extend(
        ["headnote_holding", "additional_citations", "flynote"]
    )
    fieldsets[4][1]["fields"].extend(["serial_number"])
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

    def refresh_all_content(self, request, queryset):
        from peachjam.tasks import run_ingestors

        queryset.update(last_refreshed_at=None)
        # queue up the background ingestor update task
        run_ingestors()
        self.message_user(request, "Refreshing content in the background.")

    refresh_all_content.short_description = "Refresh all content"


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


admin.site.register(
    [
        Image,
        Locality,
        CitationLink,
        Author,
        DocumentNature,
        Judge,
        MatterType,
    ]
)
admin.site.register(PeachJamSettings, PeachJamSettingsAdmin)
admin.site.register(Taxonomy, TaxonomyAdmin)
admin.site.register(GenericDocument, GenericDocumentAdmin)
admin.site.register(Legislation, LegislationAdmin)
admin.site.register(LegalInstrument, LegalInstrumentAdmin)
admin.site.register(Judgment, JudgmentAdmin)

admin.site.site_header = settings.PEACHJAM["APP_NAME"]
