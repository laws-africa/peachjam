import copy

from ckeditor.widgets import CKEditorWidget
from django import forms
from django.contrib import admin, messages
from django.contrib.admin.utils import unquote
from django.http.response import FileResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.text import capfirst
from import_export.admin import ImportMixin
from treebeard.admin import TreeAdmin
from treebeard.forms import movenodeform_factory

from peachjam.forms import IngestorForm, NewDocumentFormMixin, RelationshipForm
from peachjam.models import (
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
    Predicate,
    Relationship,
    SourceFile,
    Taxonomy,
)
from peachjam.resources import GenericDocumentResource, JudgmentResource


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


class SourceFileInline(admin.TabularInline):
    model = SourceFile
    extra = 0
    readonly_fields = ("filename", "mimetype", "attachment_link")

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


class DocumentTopicInline(admin.TabularInline):
    model = DocumentTopic
    extra = 1


class DocumentForm(forms.ModelForm):
    content_html = forms.CharField(widget=CKEditorWidget())

    def __init__(self, *args, **kwargs):
        super(DocumentForm, self).__init__(*args, **kwargs)
        if self.instance and self.instance.content_html_is_akn:
            self.fields["content_html"].widget.attrs["readonly"] = True


class DocumentAdmin(admin.ModelAdmin):
    form = DocumentForm
    inlines = [DocumentTopicInline, SourceFileInline]
    list_display = ("title", "date")
    search_fields = ("title", "date")
    readonly_fields = ("expression_frbr_uri", "work", "created_at", "updated_at")
    exclude = ("doc_type",)
    date_hierarchy = "date"

    fieldsets = [
        (
            None,
            {
                "fields": [
                    ("jurisdiction", "locality"),
                    "title",
                    "date",
                    "language",
                    "work_frbr_uri",
                ]
            },
        ),
        (None, {"fields": ["citation", "source_url"]}),
        (
            "Content",
            {
                "fields": [
                    "content_html_is_akn",
                    "content_html",
                ]
            },
        ),
        ("Advanced", {"classes": ("collapse",), "fields": ["toc_json"]}),
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


class CaseNumberAdmin(admin.TabularInline):
    model = CaseNumber
    extra = 1
    verbose_name = "Case number"
    verbose_name_plural = "Case numbers"
    readonly_fields = ["string"]
    fields = ["matter_type", "number", "year"]


class JudgmentAdmin(ImportMixin, DocumentAdmin):
    resource_class = JudgmentResource
    inlines = [CaseNumberAdmin] + DocumentAdmin.inlines
    fieldsets = copy.deepcopy(DocumentAdmin.fieldsets)
    fieldsets[0][1]["fields"].insert(1, "case_name")
    fieldsets[0][1]["fields"].extend(["author", "judges"])
    # remove work_frbr_uri, we'll generate it automatically
    fieldsets[0][1]["fields"] = [
        f for f in fieldsets[0][1]["fields"] if f != "work_frbr_uri"
    ]
    fieldsets[1][1]["fields"].insert(0, "mnc")
    fieldsets[2][1]["fields"].extend(
        ["headnote_holding", "additional_citations", "flynote"]
    )
    fieldsets[3][1]["fields"].extend(["serial_number"])
    readonly_fields = ("mnc", "serial_number", "title")


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


admin.site.register(
    [
        Image,
        Locality,
        CitationLink,
        Author,
        DocumentNature,
        Judge,
        JudgmentMediaSummaryFile,
        MatterType,
    ]
)
admin.site.register(Taxonomy, TaxonomyAdmin)
admin.site.register(GenericDocument, GenericDocumentAdmin)
admin.site.register(Legislation, LegislationAdmin)
admin.site.register(LegalInstrument, LegalInstrumentAdmin)
admin.site.register(Judgment, JudgmentAdmin)
