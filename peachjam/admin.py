from django.contrib import admin, messages
from django.contrib.admin.utils import unquote
from django.http.response import FileResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.text import capfirst
from treebeard.admin import TreeAdmin
from treebeard.forms import movenodeform_factory

from peachjam.forms import RelationshipForm
from peachjam.models import (
    CitationLink,
    AdapterSettings,
    DocumentTopic,
    Image,
    Locality,
    Predicate,
    Relationship,
    Ingestor,
    SourceFile,
    Taxonomy,
)

admin.site.register([Image, Locality, CitationLink, Ingestor, AdapterSettings])


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


class DocumentAdmin(admin.ModelAdmin):
    inlines = [DocumentTopicInline, SourceFileInline]
    list_display = ("title", "date")
    search_fields = ("title", "date")
    readonly_fields = ("expression_frbr_uri",)
    exclude = ("doc_type",)

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


admin.site.register(Taxonomy, TaxonomyAdmin)


class CoreDocumentAdmin(admin.ModelAdmin):
    inlines = [
        SourceFileInline,
    ]


@admin.register(Predicate)
class PredicateAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name", "verb")
    prepopulated_fields = {"slug": ("name",)}
    
class AdapterSettingsInline(admin.TabularInline):
    model = AdapterSettings
    extra = 1


class IngestorAdmin(admin.ModelAdmin):
    inlines = [AdapterSettingsInline]


admin.site.register(Ingestor, IngestorAdmin)
