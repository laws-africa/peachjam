from django.contrib import admin
from django.http.response import FileResponse
from django.shortcuts import get_object_or_404
from django.urls import path, reverse
from django.utils.html import format_html
from treebeard.admin import TreeAdmin
from treebeard.forms import movenodeform_factory

from peachjam.models import DocumentTopic, Image, Locality, SourceFile, Taxonomy

admin.site.register(
    [
        Image,
        Locality,
    ]
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
        return [
            path(
                "source_files/<int:pk>",
                self.admin_site.admin_view(self.download_sourcefile),
                name="peachjam_source_file",
            )
        ] + super().get_urls()

    def download_sourcefile(self, request, pk):
        source_file = get_object_or_404(SourceFile.objects, pk=pk)
        return FileResponse(source_file.file)


class TaxonomyAdmin(TreeAdmin):
    form = movenodeform_factory(Taxonomy)
    readonly_fields = ("slug",)


admin.site.register(Taxonomy, TaxonomyAdmin)
