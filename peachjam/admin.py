import copy
import json
from datetime import date

from background_task.models import Task
from ckeditor.widgets import CKEditorWidget
from countries_plus.models import Country
from dal import autocomplete
from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.contrib.contenttypes.admin import GenericStackedInline, GenericTabularInline
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http.response import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.dates import MONTHS
from django.utils.html import format_html
from django.utils.text import slugify
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from import_export.admin import ImportExportMixin as BaseImportExportMixin
from languages_plus.models import Language
from nonrelated_inlines.admin import NonrelatedStackedInline, NonrelatedTabularInline
from treebeard.admin import TreeAdmin
from treebeard.forms import MoveNodeForm, movenodeform_factory

from peachjam.extractor import ExtractorError, ExtractorService
from peachjam.forms import (
    AttachedFilesForm,
    JudgmentUploadForm,
    NewDocumentFormMixin,
    PublicationFileForm,
    RatificationForm,
    SourceFileForm,
)
from peachjam.models import (
    AlternativeName,
    Article,
    ArticleAttachment,
    AttachedFileNature,
    AttachedFiles,
    Attorney,
    Author,
    Bench,
    Book,
    CaseHistory,
    CaseNumber,
    CauseList,
    CitationLink,
    CitationProcessing,
    CoreDocument,
    Court,
    CourtClass,
    CourtDivision,
    CourtRegistry,
    DocumentNature,
    DocumentTopic,
    EntityProfile,
    ExternalDocument,
    Folder,
    Gazette,
    GenericDocument,
    Image,
    Ingestor,
    IngestorSetting,
    Journal,
    Judge,
    Judgment,
    JurisdictionProfile,
    Label,
    Legislation,
    Locality,
    LowerBench,
    MatterType,
    Outcome,
    Partner,
    PartnerLogo,
    PeachJamSettings,
    Predicate,
    PublicationFile,
    Ratification,
    RatificationCountry,
    Relationship,
    SavedDocument,
    SourceFile,
    Taxonomy,
    UserProfile,
    Work,
    citations_processor,
    pj_settings,
)
from peachjam.models.activity import EditActivity
from peachjam.plugins import plugins
from peachjam.resources import (
    ArticleResource,
    AttorneyResource,
    GazetteResource,
    GenericDocumentResource,
    JudgmentResource,
    RatificationResource,
    UserResource,
)
from peachjam.tasks import extract_citations as extract_citations_task
from peachjam.tasks import update_extracted_citations_for_a_work
from peachjam_search.tasks import search_model_saved

User = get_user_model()


class BaseAdmin(admin.ModelAdmin):
    """Base admin class for Peachjam. Includes some common fields and methods
    for all models.
    """

    def changelist_view(self, request, extra_context=None):
        resp = super().changelist_view(request, extra_context)
        if hasattr(resp, "context_data") and hasattr(self, "help_topic"):
            resp.context_data["help_topic"] = self.help_topic
        return resp


class ImportExportMixin(BaseImportExportMixin):
    def import_action(self, request, *args, **kwargs):
        resp = super().import_action(request, *args, **kwargs)
        # fix for jazzmin not using the correct field variable
        try:
            resp.context_data["fields"] = resp.context_data["fields_list"][0][1]
        except IndexError:
            pass
        return resp

    def process_result(self, result, request):
        if result.has_errors():
            # HACK
            # this allows us to show an error page if there were errors during the actual import,
            # otherwise it fails silently
            context = self.get_import_context_data()
            context["result"] = result
            context.update(self.admin_site.each_context(request))
            context["title"] = _("Import")
            context["opts"] = self.model._meta
            request.current_app = self.admin_site.name
            return TemplateResponse(request, [self.import_template_name], context)
        return super().process_result(result, request)


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

    def changelist_view(self, request, extra_context=None):
        # redirect to edit the singleton
        return redirect("admin:peachjam_peachjamsettings_change", pj_settings().pk)


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


class BaseAttachmentFileInline(admin.StackedInline):
    extra = 0
    readonly_fields = ("filename", "mimetype", "attachment_link", "size")

    def attachment_url(self, obj):
        return reverse("admin:peachjam_source_file", kwargs={"pk": obj.pk})

    def attachment_link(self, obj):
        if obj.pk:
            return format_html(
                '<a href="{url}" target="_blank">{title}</a>',
                url=self.attachment_url(obj),
                title=obj.filename,
            )


class SourceFileInline(BaseAttachmentFileInline):
    model = SourceFile
    form = SourceFileForm
    readonly_fields = (*BaseAttachmentFileInline.readonly_fields, "source_url")


class PublicationFileInline(BaseAttachmentFileInline):
    model = PublicationFile
    form = PublicationFileForm

    def attachment_url(self, obj):
        return reverse(
            "document_publication",
            kwargs={"frbr_uri": obj.document.expression_frbr_uri[1:]},
        )


class TopicChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{'-'*(obj.depth-1)} {obj.name}"


class TopicForm(forms.ModelForm):
    topic = TopicChoiceField(queryset=Taxonomy.objects.all())

    class Meta:
        model = DocumentTopic
        fields = "__all__"


class DocumentTopicInline(admin.TabularInline):
    form = TopicForm
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


class TopicTreeWidget(forms.CheckboxSelectMultiple):
    template_name = "admin/taxonomy_topic_tree.html"

    def get_context(self, name, selected, attrs):
        context = super().get_context(name, selected, attrs)
        context["topics"] = self.get_tree()
        context["selected"] = " ".join(selected) if selected else ""
        return context

    def get_tree(self):
        def fixup(item):
            item["title"] = item["data"]["name"]
            for kid in item.get("children", []):
                fixup(kid)

        tree = Taxonomy.dump_bulk()
        for x in tree:
            fixup(x)
        return tree


class TopicSelectField(forms.ModelMultipleChoiceField):
    widget = TopicTreeWidget


class DocumentForm(forms.ModelForm):
    # to track edit activity
    topics = TopicSelectField(
        required=False,
        queryset=Taxonomy.objects.all(),
        to_field_name="slug",
    )
    edit_activity_start = forms.DateTimeField(widget=forms.HiddenInput())
    edit_activity_stage = forms.CharField(widget=forms.HiddenInput())
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
    case_summary = forms.CharField(widget=CKEditorWidget(), required=False)
    order = forms.CharField(widget=CKEditorWidget(), required=False)
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
                except (ValueError, AttributeError, TypeError):
                    pass

        super().__init__(data, *args, **kwargs)

        # adjust form based on peach jam site settings
        site_settings = pj_settings()
        if "language" in self.fields:
            self.fields["language"].initial = site_settings.default_document_language
            if site_settings.document_languages.exists():
                self.fields["language"].queryset = site_settings.document_languages
        if "jurisdiction" in self.fields:
            self.fields[
                "jurisdiction"
            ].initial = site_settings.default_document_jurisdiction
            if site_settings.document_jurisdictions.exists():
                self.fields[
                    "jurisdiction"
                ].queryset = site_settings.document_jurisdictions

        if "frbr_uri_doctype" in self.fields:
            # customise doctype options for different document models
            self.fields["frbr_uri_doctype"].choices = [
                (x, x) for x in self.Meta.model.frbr_uri_doctypes
            ]

        if self.instance and self.instance.content_html_is_akn:
            self.fields["content_html"].widget.attrs["readonly"] = True

        self.fields["edit_activity_start"].initial = timezone.now()
        self.fields["edit_activity_stage"].initial = (
            "corrections" if self.instance.pk else "initial"
        )
        if self.instance.pk:
            self.fields["topics"].initial = self.instance.taxonomies.values_list(
                "topic__slug", flat=True
            )

    def full_clean(self):
        super().full_clean()
        if "content_html" in self.changed_data:
            # if the content_html has changed, set it and update related attributes
            self.instance.set_content_html(self.instance.content_html)

    def clean_content_html(self):
        # prevent CKEditor-based editing of AKN HTML
        if self.instance.content_html_is_akn:
            return self.instance.content_html
        return self.cleaned_data["content_html"]

    def create_topics(self, instance):
        topics = self.cleaned_data.get("topics", [])
        if instance.pk:
            for topic in topics:
                DocumentTopic.objects.get_or_create(document=instance, topic=topic)

            # remove any topics that are no longer selected
            DocumentTopic.objects.filter(document=instance).exclude(
                topic__in=topics
            ).delete()
        return instance

    def _save_m2m(self):
        super()._save_m2m()
        self.create_topics(self.instance)


class AttachedFilesInline(BaseAttachmentFileInline):
    model = AttachedFiles
    form = AttachedFilesForm


class ImageInline(BaseAttachmentFileInline):
    model = Image


class BackgroundTaskInline(GenericTabularInline):
    model = Task
    ct_field = "creator_content_type"
    ct_fk_field = "creator_object_id"
    fields = ("task", "run_at", "attempts", "has_error")
    readonly_fields = fields
    extra = 0
    can_delete = False

    def task(self, obj):
        return format_html(
            '<a href="{url}">{title}</a>',
            url=reverse(
                "admin:background_task_task_change",
                kwargs={
                    "object_id": obj.pk,
                },
            ),
            title=obj.task_name,
        )

    def has_error(self, obj):
        return bool(obj.last_error)


class DocumentAdmin(BaseAdmin):
    form = DocumentForm
    inlines = [
        SourceFileInline,
        PublicationFileInline,
        AlternativeNameInline,
        AttachedFilesInline,
        ImageInline,
        BackgroundTaskInline,
    ]
    list_display = (
        "title",
        "jurisdiction",
        "locality",
        "language",
        "date",
    )
    list_filter = ("jurisdiction", "locality", "nature", "language", "created_by")
    search_fields = ("title", "date")
    readonly_fields = (
        "expression_frbr_uri",
        "work",
        "created_by",
        "created_at",
        "updated_at",
        "work_frbr_uri",
        "toc_json",
        "work_link",
    )
    exclude = ("doc_type",)
    date_hierarchy = "date"
    prepopulated_fields = {"frbr_uri_number": ("title",)}
    actions = [
        "extract_citations",
        "reextract_content",
        "reindex_for_search",
        "apply_labels",
        "ensure_source_file_pdf",
        "publish",
        "unpublish",
    ]

    fieldsets = [
        (
            gettext_lazy("Key details"),
            {
                "fields": [
                    "work_link",
                    "title",
                    "jurisdiction",
                    "locality",
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
                    "created_by",
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
                    "published",
                ],
            },
        ),
        (
            gettext_lazy("Taxonomies"),
            {
                "fields": [
                    "topics",
                ]
            },
        ),
    ]

    new_document_form_mixin = NewDocumentFormMixin

    def get_inlines(self, request, obj):
        inlines = self.inlines
        if obj is None and SourceFileInline in inlines:
            inlines.remove(SourceFileInline)
        elif obj is not None and SourceFileInline not in inlines:
            inlines.append(SourceFileInline)
        return inlines

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

    def render_change_form(self, request, context, *args, **kwargs):
        # this is our only chance to inject a pre-filled field from the querystring for both add and change
        if request.GET.get("stage"):
            context["adminform"].form.fields[
                "edit_activity_stage"
            ].initial = request.GET["stage"]
        return super().render_change_form(request, context, *args, **kwargs)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user

        super().save_model(request, obj, form, change)

        # update the edit activity end time
        EditActivity.objects.create(
            document=obj,
            user=request.user,
            stage=form.cleaned_data["edit_activity_stage"],
            start=form.cleaned_data["edit_activity_start"],
            end=timezone.now(),
        )

    def save_related(self, request, form, formsets, change):
        # after saving related models, also save this model again so that it can update fields based on related changes
        # if date, title, or content changed, re-extract citations or if new document

        alternative_names_formset = [
            formset for formset in formsets if formset.model == AlternativeName
        ]

        if alternative_names_formset:
            alternative_names_has_changed = alternative_names_formset[0].has_changed()
        else:
            alternative_names_has_changed = False

        if (
            not change
            or ["date", "title", "citation"] in form.changed_data
            or alternative_names_has_changed
        ):
            cp = citations_processor()
            cp.queue_re_extract_citations(form.instance.date)

        super().save_related(request, form, formsets, change)
        form.instance.save()

        if change:
            # the source file needs to update its filename to take changes into account
            # refresh, because the source file may have been deleted
            form.instance.refresh_from_db()
            sf = getattr(form.instance, "source_file", None)
            if sf:
                sf.set_download_filename()

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
        for doc in queryset.iterator():
            extract_citations_task(doc.pk, creator=doc)
        self.message_user(
            request, f"Queued tasks to extract citations from {count} documents."
        )

    extract_citations.short_description = "Extract citations (background)"

    def reextract_content(self, request, queryset):
        """Re-extract content from source files that are Word documents, overwriting content_html."""
        count = 0
        for doc in queryset.iterator():
            if doc.extract_content_from_source_file():
                count += 1
                doc.extract_citations()
                doc.save()
        self.message_user(request, f"Re-imported content from {count} documents.")

    reextract_content.short_description = "Re-extract content from DOCX files"

    def reindex_for_search(self, request, queryset):
        """Set up a background task to re-index documents for search."""
        count = queryset.count()
        for doc in queryset.iterator():
            search_model_saved(doc._meta.label, doc.pk)
        self.message_user(request, f"Queued tasks to re-index for {count} documents.")

    reindex_for_search.short_description = "Re-index for search (background)"

    def apply_labels(self, request, queryset):
        count = queryset.count()
        for doc in queryset.iterator():
            doc.apply_labels()
        self.message_user(request, f"Applying labels for {count} documents.")

    apply_labels.short_description = "Apply labels"

    def ensure_source_file_pdf(self, request, queryset):
        count = queryset.count()
        for doc in queryset.iterator():
            if hasattr(doc, "source_file"):
                doc.source_file.ensure_file_as_pdf()
        self.message_user(request, f"Ensuring PDF for {count} documents.")

    ensure_source_file_pdf.short_description = "Ensure PDF for source file (background)"

    def has_delete_permission(self, request, obj=None):
        if obj and (
            request.user.has_perm("peachjam.can_delete_own_document")
            and obj.created_by == request.user
        ):
            return True
        return super().has_delete_permission(request, obj=obj)

    def has_change_permission(self, request, obj=None):
        if obj and (
            request.user.has_perm("peachjam.can_edit_own_document")
            and obj.created_by == request.user
        ):
            return True
        return super().has_change_permission(request, obj=obj)

    def publish(self, request, queryset):
        queryset.update(published=True)
        self.message_user(request, _("Documents published."))

    publish.short_description = gettext_lazy("Publish selected documents")

    def unpublish(self, request, queryset):
        queryset.update(published=False)
        self.message_user(request, _("Documents unpublished."))

    unpublish.short_description = gettext_lazy("Unpublish selected documents")


class TaxonomyForm(MoveNodeForm):
    def save(self, commit=True):
        super().save(commit=commit)
        # save all children so that the slugs take into account the potentially updated parent
        for node in self.instance.get_descendants():
            node.save()
        return self.instance

    def clean(self):
        if not self.errors:
            ref_node = self.cleaned_data["_ref_node_id"]
            position = self.cleaned_data["_position"]
            name = self.cleaned_data["name"]
            parent = None
            if ref_node:
                node = self.instance.__class__.objects.filter(
                    pk=self.cleaned_data["_ref_node_id"]
                ).first()
                if position == "sorted-child":
                    parent = node
                else:
                    parent = node.get_parent()
            slug = (f"{parent.slug}-" if parent else "") + slugify(name)
            qs = self.instance.__class__.objects.filter(slug=slug)
            if hasattr(self.instance, "pk"):
                qs = qs.exclude(pk=self.instance.pk)
            exists = qs.exists()
            if exists:
                raise ValidationError(
                    _('Taxonomy with slug "%(value)s" already exists.'),
                    params={"value": slug},
                    code="duplicate",
                )
        return self.cleaned_data


class TaxonomyAdmin(TreeAdmin):
    form = movenodeform_factory(Taxonomy, TaxonomyForm)
    readonly_fields = ("slug",)
    inlines = [EntityProfileInline]
    # prevent pagination
    list_per_page = 1_000_000

    def changelist_view(self, request, extra_context=None):
        resp = super().changelist_view(request, extra_context)

        def fixup(item):
            item["title"] = item["data"]["name"]
            item["href"] = reverse("admin:peachjam_taxonomy_change", args=[item["id"]])
            for kid in item.get("children", []):
                fixup(kid)

        # grab the tree and turn it into something la-table-of-contents-controller understands
        tree = self.model.dump_bulk()
        for x in tree:
            fixup(x)
        resp.context_data["tree_json"] = json.dumps(tree)

        return resp


class CoreDocumentAdmin(DocumentAdmin):
    pass


class GenericDocumentAdmin(ImportExportMixin, DocumentAdmin):
    resource_class = GenericDocumentResource
    fieldsets = copy.deepcopy(DocumentAdmin.fieldsets)
    list_display = list(DocumentAdmin.list_display) + ["nature"]
    list_filter = list(DocumentAdmin.list_filter) + ["nature", "authors"]
    filter_horizontal = ("authors",)
    fieldsets[0][1]["fields"].extend(["authors", "nature"])

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.prefetch_related("authors", "nature")
        return qs


class LegislationAdmin(ImportExportMixin, DocumentAdmin):
    fieldsets = copy.deepcopy(DocumentAdmin.fieldsets)
    fieldsets[0][1]["fields"].extend(["nature"])
    fieldsets[3][1]["fields"].extend(["metadata_json"])
    fieldsets[3][1]["fields"].extend(["commencements_json"])
    fieldsets[3][1]["fields"].extend(["timeline_json"])
    fieldsets[2][1]["classes"] = ("collapse",)
    fieldsets[4][1]["fields"].extend(["parent_work"])
    readonly_fields = ["parent_work"] + list(DocumentAdmin.readonly_fields)


class CaseNumberAdmin(admin.StackedInline):
    model = CaseNumber
    extra = 1
    verbose_name = gettext_lazy("case number")
    verbose_name_plural = gettext_lazy("case numbers")
    readonly_fields = ["string"]
    fields = ["matter_type", "number", "year", "string_override"]


class BenchInline(admin.TabularInline):
    # by using an inline, the ordering of the judges is preserved
    model = Bench
    extra = 3
    verbose_name = gettext_lazy("judge")
    verbose_name_plural = gettext_lazy("judges")


class LowerBenchInline(admin.TabularInline):
    model = LowerBench
    extra = 3
    verbose_name = gettext_lazy("lower court judge")
    verbose_name_plural = gettext_lazy("lower court judges")


class JudgmentRelationshipStackedInline(NonrelatedTabularInline):
    model = Relationship
    fields = ["predicate", "object_work"]
    verbose_name = "Related judgment"
    verbose_name_plural = "Related judgments"
    extra = 2

    def get_form_queryset(self, obj):
        return Relationship.objects.filter(subject_work=obj.work)

    def save_new_instance(self, parent, instance):
        instance.subject_work = parent.work

    def get_formset(self, request, obj=None, **kwargs):
        return super().get_formset(
            request,
            obj,
            widgets={
                "object_work": autocomplete.ModelSelect2(url="autocomplete-works")
            },
            **kwargs,
        )


class CaseHistoryInlineAdmin(NonrelatedStackedInline):
    model = CaseHistory
    verbose_name = verbose_name_plural = "case history"
    exclude = ["judgment_work"]
    extra = 1

    def get_form_queryset(self, obj):
        return CaseHistory.objects.filter(judgment_work=obj.work)

    def save_new_instance(self, parent, instance):
        instance.judgment_work = parent.work

    def get_formset(self, request, obj=None, **kwargs):
        return super().get_formset(
            request,
            obj,
            widgets={
                "historical_judgment_work": autocomplete.ModelSelect2(
                    url="autocomplete-judgment-works"
                )
            },
            **kwargs,
        )


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


class JudgmentAdmin(ImportExportMixin, DocumentAdmin):
    help_topic = "judgments/upload-a-judgment"
    form = JudgmentAdminForm
    resource_class = JudgmentResource
    inlines = [
        BenchInline,
        LowerBenchInline,
        CaseNumberAdmin,
        CaseHistoryInlineAdmin,
        JudgmentRelationshipStackedInline,
    ] + DocumentAdmin.inlines
    filter_horizontal = ("judges", "attorneys", "outcomes")
    list_filter = (*DocumentAdmin.list_filter, "court")
    fieldsets = copy.deepcopy(DocumentAdmin.fieldsets)

    fieldsets[0][1]["fields"].insert(3, "court")
    fieldsets[0][1]["fields"].insert(4, "registry")
    fieldsets[0][1]["fields"].insert(5, "case_name")
    fieldsets[0][1]["fields"].append("mnc")
    fieldsets[0][1]["fields"].append("hearing_date")
    fieldsets[0][1]["fields"].append("outcomes")
    fieldsets[0][1]["fields"].append("serial_number")
    fieldsets[0][1]["fields"].append("serial_number_override")

    fieldsets[1][1]["fields"].insert(0, "attorneys")

    fieldsets[2][1]["classes"] = ["collapse"]
    fieldsets[3][1]["fields"].extend(["case_summary", "flynote", "order"])
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
    jazzmin_section_order = (
        "Key details",
        "Case numbers",
        "Judges",
        "Additional details",
        "Content",
        "Alternative names",
        "Attached files",
        "Document topics",
        "Work identification",
        "Advanced",
    )

    class Media:
        js = ("js/judgment_duplicates.js",)

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["can_upload_document"] = ExtractorService().enabled()
        extra_context["upload_url"] = reverse("admin:peachjam_judgment_upload")
        return super().changelist_view(request, extra_context)

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)

        if not request.user.has_perm("peachjam.can_edit_advanced_fields"):
            # Users without permission to edit advanced fields can't view the
            # Advanced and Work identification fieldsets
            return [
                x
                for x in fieldsets
                if x[0]
                not in [
                    gettext_lazy("Advanced"),
                    gettext_lazy("Work identification"),
                ]
            ]

        return fieldsets

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "upload/",
                self.admin_site.admin_view(self.upload_view),
                name="peachjam_judgment_upload",
            ),
        ]
        return custom_urls + urls

    def upload_view(self, request):
        extractor = ExtractorService()
        if not extractor.enabled():
            messages.error(
                request,
                _(
                    "The Laws.Africa extractor is not enabled. Please check your settings."
                ),
            )
            return redirect("admin:peachjam_judgment_changelist")

        form = JudgmentUploadForm(
            initial={"jurisdiction": pj_settings().default_document_jurisdiction}
        )

        # Custom logic for the upload view
        if request.method == "POST":
            form = JudgmentUploadForm(
                request.POST,
                request.FILES,
            )
            if form.is_valid():
                try:
                    with transaction.atomic():
                        doc = extractor.extract_judgment_from_file(
                            jurisdiction=form.cleaned_data["jurisdiction"],
                            file=form.cleaned_data["file"],
                        )
                    messages.success(
                        request, _("Judgment uploaded. Please check details carefully.")
                    )
                    url = (
                        reverse("admin:peachjam_judgment_change", args=[doc.pk])
                        + "?stage=after-extraction"
                    )
                    return redirect(url)
                except ExtractorError as e:
                    form.add_error(None, str(e))

        context = {
            "form": form,
        }
        return render(request, "admin/judgment_upload_form.html", context)


@admin.register(CauseList)
class CauseListAdmin(DocumentAdmin):
    fieldsets = copy.deepcopy(DocumentAdmin.fieldsets)
    fieldsets[0][1]["fields"].insert(3, "court")
    fieldsets[0][1]["fields"].insert(3, "judges")


@admin.register(Predicate)
class PredicateAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name", "verb")
    prepopulated_fields = {"slug": ("name",)}


class IngestorSettingInline(admin.TabularInline):
    model = IngestorSetting
    extra = 3


class IngestorForm(forms.ModelForm):
    adapter = forms.ChoiceField(
        choices=lambda: [(y, y) for y in plugins.registry["ingestor-adapter"].keys()]
    )

    class Meta:
        model = Ingestor
        fields = (
            "adapter",
            "name",
            "last_refreshed_at",
            "repeat",
            "schedule",
            "enabled",
        )

    def save(self, *args, **kwargs):
        instance = super().save(*args, **kwargs)
        instance.queue_task()
        return instance


@admin.register(Ingestor)
class IngestorAdmin(admin.ModelAdmin):
    inlines = [IngestorSettingInline]
    actions = ["refresh_all_content", "update_latest_content"]
    list_display = ("name", "adapter", "last_refreshed_at", "enabled")
    form = IngestorForm

    def refresh_all_content(self, request, queryset):
        queryset.update(last_refreshed_at=None)
        for ing in queryset:
            # queue up the background ingestor update task
            ing.queue_task()
        self.message_user(
            request,
            _("Refreshing all content for selected ingestors in the background."),
        )

    refresh_all_content.short_description = gettext_lazy(
        "Refresh all content for selected ingestors - Full update"
    )

    def update_latest_content(self, request, queryset):
        for ing in queryset:
            ing.queue_task()
        self.message_user(
            request, _("Getting content since last update in background.")
        )

    update_latest_content.short_description = gettext_lazy(
        "Update content for selected ingestors - Latest updates"
    )


class ArticleAttachmentInline(BaseAttachmentFileInline):
    model = ArticleAttachment
    extra = 1

    def attachment_url(self, obj):
        return obj.get_absolute_url()

    def attachment_link(self, obj):
        if obj.pk:
            return format_html(
                '<a href="{url}" target="_blank">{url}</a>',
                url=self.attachment_url(obj),
            )

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)

        original_init = formset.form.__init__

        def new_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            instance = kwargs.get("instance", None)

            if instance and instance.file:
                # Make the file field readonly by making it disabled in the widget
                self.fields["file"].widget.attrs["readonly"] = True
                self.fields["file"].widget.attrs["disabled"] = "disabled"

        formset.form.__init__ = new_init
        return formset


class ArticleForm(forms.ModelForm):
    body = forms.CharField(widget=CKEditorWidget())
    topics = forms.ModelMultipleChoiceField(
        queryset=Article.get_article_tags_root().get_children()
    )


@admin.register(Article)
class ArticleAdmin(ImportExportMixin, admin.ModelAdmin):
    resource_class = ArticleResource
    inlines = [ArticleAttachmentInline]
    form = ArticleForm
    list_display = ("title", "author", "date", "published")
    list_display_links = ("title",)
    list_filter = ("published", "author")
    search_fields = ("title", "body")
    date_hierarchy = "date"
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
    actions = ["publish", "unpublish"]

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields["author"].initial = request.user
        if not request.user.is_superuser:
            # limit author choices to the current user
            form.base_fields["author"].queryset = request.user.__class__.objects.filter(
                pk=request.user.pk
            )
        return form

    def publish(self, request, queryset):
        queryset.update(published=True)
        self.message_user(request, _("Articles published."))

    publish.short_description = gettext_lazy("Publish selected articles")

    def unpublish(self, request, queryset):
        queryset.update(published=False)
        self.message_user(request, _("Articles unpublished."))

    unpublish.short_description = gettext_lazy("Unpublish selected articles")


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    pass


class RelationshipInline(admin.TabularInline):
    model = Relationship
    fk_name = "subject_work"
    fields = ("predicate", "object_work")

    def get_formset(self, request, obj=None, **kwargs):
        return super().get_formset(
            request,
            obj,
            widgets={
                "object_work": autocomplete.ModelSelect2(url="autocomplete-works")
            },
            **kwargs,
        )


class DocumentInline(admin.TabularInline):
    model = CoreDocument
    fields = ("link", "language")
    readonly_fields = fields
    can_delete = False
    extra = 0

    def link(self, obj):
        url = reverse("admin:peachjam_coredocument_change", args=[obj.pk])
        return format_html('<a href="{}">{}</a>', url, obj.title)

    link.short_description = "Document"


@admin.register(Work)
class WorkAdmin(admin.ModelAdmin):
    fields = (
        "title",
        "frbr_uri",
        "languages",
        "ranking",
        "frbr_uri_country",
        "frbr_uri_locality",
        "frbr_uri_doctype",
        "frbr_uri_subtype",
        "frbr_uri_actor",
        "frbr_uri_date",
        "frbr_uri_number",
        "partner",
    )
    search_fields = (
        "title",
        "frbr_uri",
    )
    list_filter = (
        "frbr_uri_country",
        "frbr_uri_doctype",
        "frbr_uri_subtype",
        "frbr_uri_actor",
    )
    list_display = ("title", "frbr_uri", "languages", "ranking")
    readonly_fields = [f for f in fields if f != "partner"]
    inlines = [RelationshipInline, DocumentInline]
    actions = ["update_extracted_citations", "update_languages"]

    def has_add_permission(self, request):
        # disallow adding works, they are managed automatically
        return False

    def update_extracted_citations(self, request, queryset):
        count = queryset.count()
        for work in queryset:
            update_extracted_citations_for_a_work(work.pk)
        self.message_user(
            request, f"Queued tasks to update extracted citations for {count} works."
        )

    update_extracted_citations.short_description = (
        "Update extracted citations (background)"
    )

    def update_languages(self, request, queryset):
        count = queryset.count()
        for work in queryset:
            work.update_languages()
        self.message_user(request, f"Updated languages for {count} works.")

    update_languages.short_description = "Update languages"


@admin.register(DocumentNature)
class DocumentNatureAdmin(admin.ModelAdmin):
    search_fields = ("name", "code")
    list_display = ("name", "code")
    prepopulated_fields = {"code": ("name",)}


@admin.register(Court)
class CourtAdmin(admin.ModelAdmin):
    inlines = [EntityProfileInline]
    list_display = ("name", "code")
    search_fields = ("name", "code")


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    inlines = [EntityProfileInline]


@admin.register(Gazette)
class GazetteAdmin(ImportExportMixin, DocumentAdmin):
    resource_class = GazetteResource
    inlines = [
        SourceFileInline,
        BackgroundTaskInline,
    ]
    prepopulated_fields = {}

    fieldsets = copy.deepcopy(DocumentAdmin.fieldsets)
    fieldsets[2][1]["fields"].remove("frbr_uri_number")
    fieldsets[0][1]["fields"].extend(
        [
            "frbr_uri_number",
            "volume_number",
            "supplement",
            "supplement_number",
            "special",
        ]
    )
    fieldsets[1][1]["fields"].remove("citation")
    fieldsets[1][1]["fields"].remove("source_url")
    fieldsets[4][1]["fields"].remove("toc_json")
    fieldsets[4][1]["fields"].remove("content_html_is_akn")
    fieldsets[4][1]["fields"].extend(["publication", "sub_publication"])
    # remove content fieldset
    fieldsets.pop(3)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields["frbr_uri_number"].label = gettext_lazy("Gazette number")
        return form


@admin.register(Book)
class BookAdmin(DocumentAdmin):
    fieldsets = copy.deepcopy(DocumentAdmin.fieldsets)
    fieldsets[3][1]["fields"].insert(3, "content_markdown")

    class Media:
        js = (
            "https://cdn.jsdelivr.net/npm/@lawsafrica/law-widgets@latest/dist/lawwidgets/lawwidgets.js",
        )

    def save_model(self, request, obj, form, change):
        if "content_markdown" in form.changed_data:
            obj.convert_content_markdown()

        resp = super().save_model(request, obj, form, change)

        if "content_markdown" in form.changed_data:
            obj.extract_citations()

        return resp


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


@admin.register(CourtRegistry)
class CourtRegistryAdmin(BaseAdmin):
    help_topic = "site-admin/add-court-registries"
    readonly_fields = ("code",)
    list_display = ("name", "code")


@admin.register(Outcome)
class OutcomeAdmin(admin.ModelAdmin):
    list_display = ("name",)


class UserAdminCustom(ImportExportMixin, UserAdmin):
    resource_class = UserResource


@admin.register(Label)
class LabelAdmin(admin.ModelAdmin):
    list_display = ("name", "code")
    prepopulated_fields = {"code": ("name",)}


@admin.register(Locality)
class LocalityAdmin(admin.ModelAdmin):
    list_display = ("name", "jurisdiction", "code")
    prepopulated_fields = {"code": ("name",)}
    search_fields = ("name", "code")
    inlines = [EntityProfileInline]


@admin.register(JurisdictionProfile)
class JurisdictionProfileAdmin(admin.ModelAdmin):
    list_display = ("jurisdiction",)
    inlines = [EntityProfileInline]


@admin.register(Judge)
class JudgeAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(MatterType)
class MatterTypeAdmin(BaseAdmin):
    help_topic = "site-admin/add-matter-types"


@admin.register(Attorney)
class AttorneyAdmin(ImportExportMixin, admin.ModelAdmin):
    resource_class = AttorneyResource
    list_display = ("name", "description")


class RatificationCountryAdmin(admin.StackedInline):
    model = RatificationCountry
    extra = 1

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "country":
            kwargs["queryset"] = Country.objects.filter(continent="AF")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Ratification)
class RatificationAdmin(ImportExportMixin, admin.ModelAdmin):
    inlines = (RatificationCountryAdmin,)
    form = RatificationForm
    resource_class = RatificationResource
    search_fields = ("work__title",)


class PartnerForm(forms.ModelForm):
    document_blurb_html = forms.CharField(
        widget=CKEditorWidget(),
        required=False,
    )

    class Meta:
        model = Partner
        exclude = []


class PartnerLogoInline(BaseAttachmentFileInline):
    model = PartnerLogo
    extra = 1

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)

        original_init = formset.form.__init__

        def new_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            instance = kwargs.get("instance", None)

            if instance and instance.file:
                # Make the file field readonly by making it disabled in the widget
                self.fields["file"].widget.attrs["readonly"] = True
                self.fields["file"].widget.attrs["disabled"] = "disabled"

        formset.form.__init__ = new_init
        return formset


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    inlines = [PartnerLogoInline]
    form = PartnerForm


admin.site.register(
    [
        CitationLink,
        CourtClass,
        CourtDivision,
        AttachedFileNature,
        CitationProcessing,
        Folder,
        SavedDocument,
    ]
)
admin.site.register(PeachJamSettings, PeachJamSettingsAdmin)
admin.site.register(Taxonomy, TaxonomyAdmin)
admin.site.register(CoreDocument, CoreDocumentAdmin)
admin.site.register(GenericDocument, GenericDocumentAdmin)
admin.site.register(Legislation, LegislationAdmin)
admin.site.register(Judgment, JudgmentAdmin)

admin.site.unregister(User)
admin.site.register(User, UserAdminCustom)

admin.site.site_header = settings.PEACHJAM["APP_NAME"]
