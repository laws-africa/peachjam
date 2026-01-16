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
from django.contrib.admin.utils import flatten_fieldsets, quote
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.admin import GenericStackedInline, GenericTabularInline
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http.response import FileResponse, HttpResponse, HttpResponseRedirect
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
from guardian.admin import GuardedModelAdminMixin
from guardian.shortcuts import assign_perm, get_groups_with_perms, remove_perm
from import_export.admin import ImportExportMixin as BaseImportExportMixin
from languages_plus.models import Language
from nonrelated_inlines.admin import NonrelatedStackedInline, NonrelatedTabularInline
from treebeard.admin import TreeAdmin
from treebeard.forms import MoveNodeForm, movenodeform_factory

from peachjam.extractor import ExtractorError, ExtractorService
from peachjam.forms import (
    AttachedFilesForm,
    GuardianGroupForm,
    GuardianUserForm,
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
    Bill,
    Book,
    CaseAction,
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
    CustomProperty,
    CustomPropertyLabel,
    DocumentAccessGroup,
    DocumentNature,
    DocumentTopic,
    EntityProfile,
    ExternalDocument,
    Gazette,
    GenericDocument,
    Image,
    Ingestor,
    IngestorSetting,
    JournalArticle,
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
    ProvisionEnrichment,
    PublicationFile,
    Ratification,
    RatificationCountry,
    Relationship,
    SourceFile,
    Taxonomy,
    Treatment,
    UncommencedProvision,
    UnconstitutionalProvision,
    UserFollowing,
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
    BillResource,
    GazetteResource,
    GenericDocumentResource,
    JudgmentResource,
    RatificationResource,
    UserResource,
)
from peachjam.tasks import extract_citations as extract_citations_task
from peachjam.tasks import (
    generate_judgment_summary,
    update_extracted_citations_for_a_work,
)
from peachjam_search.models import SavedSearch
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
    def import_action(self, request, **kwargs):
        resp = super().import_action(request, **kwargs)
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


@admin.register(PeachJamSettings)
class PeachJamSettingsAdmin(admin.ModelAdmin):
    filter_horizontal = (
        "document_languages",
        "document_jurisdictions",
    )

    def has_add_permission(self, request):
        return False

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
    readonly_fields = (
        *BaseAttachmentFileInline.readonly_fields,
        "source_url",
        "sha256",
        "anonymised_file_as_pdf",
    )


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

        # start attribute-level tracking
        self.instance.track_changes()

    def full_clean(self):
        super().full_clean()
        if "content_html" in self.changed_data:
            # if the content_html has changed, set it and update related attributes
            self.instance.set_content_html(self.instance.content_html)
            if self.instance.pk:
                self.instance.update_text_content()

    def clean_content_html(self):
        # prevent CKEditor-based editing of AKN HTML
        if self.instance.content_html_is_akn:
            return self.instance.content_html
        return self.cleaned_data["content_html"]

    def create_topics(self, instance):
        topics = self.cleaned_data.get("topics", [])
        if instance.pk:
            # sanitise topics so that only the lowest level topic is used
            topics = Taxonomy.limit_to_lowest(topics)
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

    @property
    def extractor_url(self):
        """URL to use if this document type supports the extractor service."""
        extractor = ExtractorService()
        if extractor.enabled() and isinstance(self.instance, Judgment):
            return reverse("admin:peachjam_extract_judgment")


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


class CustomPropertyInline(admin.TabularInline):
    model = CustomProperty


class AccessGroupForm(forms.Form):
    groups = forms.ModelMultipleChoiceField(
        queryset=DocumentAccessGroup.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    def __init__(self, *args, obj=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.obj = obj
        groups = DocumentAccessGroup.objects.filter(
            group__in=get_groups_with_perms(obj)
        )
        self.fields["groups"].initial = groups

    def set_access_groups(self):
        add_groups = self.cleaned_data["groups"]
        remove_groups = DocumentAccessGroup.objects.exclude(pk__in=add_groups)
        content_type = ContentType.objects.get_for_model(self.obj)
        view_perm = Permission.objects.get(
            content_type=content_type, codename=f"view_{content_type.model}"
        )

        for group in add_groups:
            assign_perm(view_perm, group.group, self.obj)

        for group in remove_groups:
            remove_perm(view_perm, group.group, self.obj)


# better forms for django guardian admin views
GuardedModelAdminMixin.get_obj_perms_group_select_form = (
    lambda self, request: GuardianGroupForm
)
GuardedModelAdminMixin.get_obj_perms_user_select_form = (
    lambda self, request: GuardianUserForm
)


class AccessGroupMixin(GuardedModelAdminMixin):
    change_form_template = None
    obj_perms_manage_template = (
        "admin/guardian/model/obj_perms_manage_access_groups.html"
    )

    def obj_perms_manage_view(self, request, object_pk):
        from django.contrib.admin.utils import unquote

        template_name = self.get_obj_perms_manage_template()
        obj = get_object_or_404(self.get_queryset(request), pk=unquote(object_pk))
        context = self.get_obj_perms_base_context(request, obj)
        context.update(
            {
                "access_group_form": AccessGroupForm(obj=obj),
            }
        )

        if request.method == "POST" and "set_access_group" in request.POST:
            form = AccessGroupForm(request.POST, obj=obj)
            if form.is_valid():
                form.set_access_groups()
                messages.success(request, _("Access groups updated."))
                return HttpResponseRedirect(".")
            context["access_group_form"] = form

        return render(request, template_name, context)

    def document_access_link(self, obj):
        if obj and obj.id:
            url = reverse(
                f"admin:{obj._meta.app_label}_{obj._meta.model_name}_permissions",
                args=[quote(obj.pk)],
            )
            return format_html(
                '<a href="{}">{}</a>',
                url,
                _("Manage restricted access groups"),
            )
        return "-"

    document_access_link.short_description = gettext_lazy("Restricted access groups")


class DocumentAdmin(AccessGroupMixin, BaseAdmin):
    # used in change_form.html
    is_document_admin = True
    form = DocumentForm
    inlines = [
        SourceFileInline,
        PublicationFileInline,
        AlternativeNameInline,
        AttachedFilesInline,
        ImageInline,
        CustomPropertyInline,
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
        "metadata_json",
        "work_link",
        "document_access_link",
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
                    "published",
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
                    "content_html_is_akn",
                    "allow_robots",
                    "restricted",
                    "document_access_link",
                    "toc_json",
                    "metadata_json",
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

    work_link.short_description = gettext_lazy("Work")

    def download_sourcefile(self, request, pk):
        source_file = get_object_or_404(SourceFile.objects, pk=pk)
        return FileResponse(source_file.file)

    def extract_citations(self, request, queryset):
        count = queryset.count()
        for doc in queryset.only("pk"):
            extract_citations_task(doc.pk, creator=doc)
        self.message_user(
            request,
            _("Queued tasks to extract citations from %(count)d documents.")
            % {"count": count},
        )

    extract_citations.short_description = gettext_lazy("Extract citations (background)")

    def reextract_content(self, request, queryset):
        """Re-extract content from source files that are Word documents, overwriting content_html."""
        count = 0
        with transaction.atomic():
            for doc in queryset.only("pk"):
                if doc.extract_content_from_source_file():
                    count += 1
                    doc.extract_citations()
                    doc.save()
        self.message_user(
            request,
            _("Re-imported content from %(count)d documents.") % {"count": count},
        )

    reextract_content.short_description = gettext_lazy(
        "Re-extract content from DOCX files"
    )

    def reindex_for_search(self, request, queryset):
        """Set up a background task to re-index documents for search."""
        count = queryset.count()
        for doc in queryset.only("pk"):
            search_model_saved(doc._meta.label, doc.pk)
        self.message_user(
            request,
            _("Queued tasks to re-index for %(count)d documents.") % {"count": count},
        )

    reindex_for_search.short_description = gettext_lazy(
        "Re-index for search (background)"
    )

    def apply_labels(self, request, queryset):
        with transaction.atomic():
            count = queryset.count()
            for doc in queryset.all():
                if doc.decorator:
                    doc.decorator.apply_labels(doc)
        self.message_user(
            request, _("Applying labels for %(count)d documents.") % {"count": count}
        )

    apply_labels.short_description = gettext_lazy("Apply labels")

    def ensure_source_file_pdf(self, request, queryset):
        with transaction.atomic():
            count = queryset.count()
            for doc in queryset.all():
                if hasattr(doc, "source_file"):
                    doc.source_file.ensure_file_as_pdf()
        self.message_user(
            request, _("Ensuring PDF for %(count)d documents.") % {"count": count}
        )

    ensure_source_file_pdf.short_description = gettext_lazy(
        "Ensure PDF for source file (background)"
    )

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
        with transaction.atomic():
            queryset.update(published=True)
        self.message_user(request, _("Documents published."))

    publish.short_description = gettext_lazy("Publish selected documents")

    def unpublish(self, request, queryset):
        with transaction.atomic():
            queryset.update(published=False)
        self.message_user(request, _("Documents unpublished."))

    unpublish.short_description = gettext_lazy("Unpublish selected documents")


class TaxonomyForm(MoveNodeForm):
    def save(self, commit=True):
        super().save(commit=commit)
        # save all children so that the slugs take into account the potentially updated parent
        for node in self.instance.get_descendants():
            if "show_in_document_listing" in self.changed_data:
                # if the show_in_document_listing field has changed, update all children to match
                node.show_in_document_listing = self.instance.show_in_document_listing
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


@admin.register(Taxonomy)
class TaxonomyAdmin(AccessGroupMixin, TreeAdmin):
    form = movenodeform_factory(Taxonomy, TaxonomyForm)
    readonly_fields = ("slug", "path_name", "document_access_link")
    inlines = [EntityProfileInline]
    # prevent pagination
    list_per_page = 1_000_000

    def get_readonly_fields(self, request, obj=None):
        return list(super().get_readonly_fields(request, obj)) + [
            a.name for a in Taxonomy._meta.fields if a.name.startswith("path_name_")
        ]

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


@admin.register(CoreDocument)
class CoreDocumentAdmin(DocumentAdmin):
    def has_add_permission(self, request):
        # this is prevented because there is no view that handles a CoreDocument
        return False


@admin.register(GenericDocument)
class GenericDocumentAdmin(ImportExportMixin, DocumentAdmin):
    resource_classes = [GenericDocumentResource]
    fieldsets = copy.deepcopy(DocumentAdmin.fieldsets)
    list_display = list(DocumentAdmin.list_display) + ["nature"]
    list_filter = list(DocumentAdmin.list_filter) + ["nature", "author"]
    filter_horizontal = ("author",)
    fieldsets[0][1]["fields"].extend(["author", "nature"])

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.prefetch_related("author", "nature")
        return qs


@admin.register(Legislation)
class LegislationAdmin(ImportExportMixin, DocumentAdmin):
    fieldsets = copy.deepcopy(DocumentAdmin.fieldsets)
    fieldsets[0][1]["fields"].extend(["nature"])
    fieldsets[2][1]["classes"] = ("collapse",)
    fieldsets[4][1]["fields"].extend(
        ["parent_work", "commencements_json", "timeline_json"]
    )
    readonly_fields = ["parent_work", "commencements_json", "timeline_json"] + list(
        DocumentAdmin.readonly_fields
    )


@admin.register(Bill)
class BillAdmin(ImportExportMixin, DocumentAdmin):
    resource_classes = [BillResource]
    fieldsets = copy.deepcopy(DocumentAdmin.fieldsets)
    fieldsets[0][1]["fields"].extend(["author"])


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

    def get_formset(self, request, obj=None, **kwargs):
        return super().get_formset(
            request,
            obj,
            widgets={"judge": autocomplete.ModelSelect2(url="autocomplete-judges")},
            **kwargs,
        )


class LowerBenchInline(admin.TabularInline):
    model = LowerBench
    extra = 3
    verbose_name = gettext_lazy("lower court judge")
    verbose_name_plural = gettext_lazy("lower court judges")

    def get_formset(self, request, obj=None, **kwargs):
        return super().get_formset(
            request,
            obj,
            widgets={"judge": autocomplete.ModelSelect2(url="autocomplete-judges")},
            **kwargs,
        )


class JudgmentRelationshipStackedInline(NonrelatedTabularInline):
    model = Relationship
    fields = ["predicate", "object_work"]
    verbose_name = gettext_lazy("Related judgment")
    verbose_name_plural = gettext_lazy("Related judgments")
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
    verbose_name = verbose_name_plural = gettext_lazy("case history")
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
                ),
                "judges": autocomplete.ModelSelect2Multiple(url="autocomplete-judges"),
            },
            **kwargs,
        )


class JudgmentAdminForm(DocumentForm):
    hearing_date = forms.DateField(widget=DateSelectorWidget(), required=False)
    held = forms.CharField(
        widget=forms.Textarea(attrs={"style": "width: 100%; white-space: nowrap;"}),
        required=False,
    )
    issues = forms.CharField(
        widget=forms.Textarea(attrs={"style": "width: 100%; white-space: nowrap;"}),
        required=False,
    )

    class Meta:
        model = Judgment
        fields = ("hearing_date",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial["held"] = self.convert_to_paragraphs(
            self.instance.held if self.instance else []
        )
        self.initial["issues"] = self.convert_to_paragraphs(
            self.instance.issues if self.instance else []
        )

    def clean_held(self):
        return self.cleaned_data["held"].splitlines()

    def clean_issues(self):
        return self.cleaned_data["issues"].splitlines()

    def save(self, *args, **kwargs):
        if (
            "serial_number_override" in self.changed_data
            and not self.cleaned_data["serial_number_override"]
        ):
            # if the serial number override is reset, then also clear the serial number so that it is
            # re-assigned
            self.instance.serial_number = None
        super().save(*args, **kwargs)

        return self.instance

    def convert_to_paragraphs(self, value):
        if not value:
            return ""

        if isinstance(value, list):
            return "\n".join(value)

        return value


@admin.register(Judgment)
class JudgmentAdmin(ImportExportMixin, DocumentAdmin):
    help_topic = "judgments/upload-a-judgment"
    form = JudgmentAdminForm
    resource_classes = [JudgmentResource]
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

    fieldsets[0][1]["fields"].insert(4, "court")
    fieldsets[0][1]["fields"].insert(5, "registry")
    fieldsets[0][1]["fields"].insert(6, "division")
    fieldsets[0][1]["fields"].insert(7, "case_name")
    fieldsets[0][1]["fields"].append("hearing_date")
    fieldsets[0][1]["fields"].append("must_be_anonymised")
    fieldsets[0][1]["fields"].append("anonymised")
    fieldsets[0][1]["fields"].append("case_action")
    fieldsets[0][1]["fields"].append("outcomes")
    fieldsets[0][1]["fields"].append("mnc")
    fieldsets[0][1]["fields"].append("serial_number")
    fieldsets[0][1]["fields"].append("serial_number_override")

    fieldsets[1][1]["fields"].insert(0, "attorneys")

    fieldsets[2][1]["classes"] = ["collapse"]
    fieldsets.insert(
        4,
        (
            gettext_lazy("Summary"),
            {
                "fields": [
                    "case_summary_public",
                    "blurb",
                    "flynote",
                    "case_summary",
                    "issues",
                    "held",
                    "order",
                ]
            },
        ),
    ),
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
        "Summary",
        "Alternative names",
        "Attached files",
        "Document topics",
        "Work identification",
        "Advanced",
    )

    actions = DocumentAdmin.actions + [
        "generate_summary",
    ]

    class Media:
        js = ("js/judgment_duplicates.js",)

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
                "extract/",
                self.admin_site.admin_view(self.extract_view),
                name="peachjam_extract_judgment",
            ),
            path(
                "<int:object_id>/generate-summary/",
                self.admin_site.admin_view(self.generate_summary_view),
                name="peachjam_generate_summary",
            ),
        ]
        return custom_urls + urls

    def extract_view(self, request):
        """Special view that is submitted via AJAX which extracts judgment data from a file, and re-renders
        various form elements which are then injected back into the page.
        """
        extractor = ExtractorService()
        file = request.FILES.get("file")
        if not extractor.enabled() or request.method != "POST" or not file:
            return HttpResponse()

        error = None
        details = {}
        try:
            if settings.DEBUG:
                # for testing
                details = {
                    "language": "afr",
                    "court": "Continental Court",
                    "date": "2025-02-03",
                    "judges": ["Anukam J", "Eno R", "Plasket JA", "Maya P"],
                    "must_be_anonymised": True,
                    "case_numbers": [
                        {
                            "matter_type": "Criminal Case",
                            "case_number_string": "123/2025",
                            "number": None,
                            "year": 2025,
                        },
                    ],
                }
            else:
                details = extractor.extract_judgment_details(
                    pj_settings().default_document_jurisdiction, file
                )
        except ExtractorError as e:
            error = e

        # turn references into Django objects
        extractor.process_judgment_details(details)

        # prepare form data
        inlines = []
        formsets = []

        if details.get("judges"):
            judges = [{"judge": j} for j in details["judges"]]
            # make it pretty for the template
            details["judges"] = "; ".join(str(j) for j in details["judges"])

            # prepare the formset
            inline = BenchInline(Judgment, self.admin_site)
            inline.extra = len(judges) + inline.extra
            inlines.append(inline)
            formsets.append(inline.get_formset(request)(initial=judges))

        if details.get("case_numbers"):
            case_numbers = [
                {
                    "matter_type": cn.matter_type,
                    "number": cn.number,
                    "year": cn.year,
                    "string_override": cn.string_override,
                }
                for cn in details["case_numbers"]
            ]
            # make it pretty for the template
            details["case_numbers"] = "; ".join(
                cn.get_case_number_string() for cn in details["case_numbers"]
            )

            # prepare the formset
            inline = CaseNumberAdmin(Judgment, self.admin_site)
            inline.extra = len(case_numbers) + inline.extra
            inlines.append(inline)
            formsets.append(inline.get_formset(request)(initial=case_numbers))

        if not pj_settings().allow_anonymisation:
            # if anonymisation is not enabled, set must_be_anonymised to False
            details["must_be_anonymised"] = False

        judgment = Judgment()
        for field in [
            "language",
            "court",
            "case_name",
            "date",
            "hearing_date",
            "must_be_anonymised",
        ]:
            setattr(judgment, field, details.get(field))

        formsets = self.get_inline_formsets(request, formsets, inlines)
        fieldsets = self.get_fieldsets(request, None)
        ModelForm = self.get_form(
            request, None, change=False, fields=flatten_fieldsets(fieldsets)
        )
        form = ModelForm(instance=judgment)

        context = {
            "form": form,
            "formsets": formsets,
            "error": error,
            "details": details,
        }

        return render(request, "admin/peachjam/judgment/_extracted_form.html", context)

    def generate_summary(self, request, queryset):
        """Generate a summary for the selected judgments."""

        # check if the user has permission to generate summaries
        if not request.user.has_perm("peachjam.can_generate_judgment_summary"):
            self.message_user(
                request,
                _("You do not have permission to generate judgment summaries."),
            )
            return

        count = queryset.count()
        for doc in queryset.only("pk"):
            generate_judgment_summary(doc.pk)
        self.message_user(
            request,
            _("Generating summaries for %(count)d judgments.") % {"count": count},
        )

    def generate_summary_view(self, request, object_id):
        if request.user.has_perm("peachjam.can_generate_judgment_summary"):
            message = _("Generating summary for judgment with ID: {}").format(object_id)
            generate_judgment_summary(object_id)
            self.message_user(request, message)
        else:
            message = _("You do not have permission to generate judgment summaries.")
            self.message_user(request, message)

        return redirect(
            reverse(
                "admin:%s_%s_change"
                % (self.model._meta.app_label, self.model._meta.model_name),
                args=[object_id],
            )
        )

    generate_summary.short_description = gettext_lazy("Generate summaries (background)")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        obj.ensure_anonymised_source_file()


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
    body = forms.CharField(widget=CKEditorWidget("article"))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["topics"].queryset = Article.get_article_tags_root().get_children()


@admin.register(Article)
class ArticleAdmin(ImportExportMixin, admin.ModelAdmin):
    resource_classes = [ArticleResource]
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
        "featured",
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
        with transaction.atomic():
            queryset.update(published=True)
        self.message_user(request, _("Articles published."))

    publish.short_description = gettext_lazy("Publish selected articles")

    def unpublish(self, request, queryset):
        with transaction.atomic():
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
        "authority_score",
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
    list_display = ("title", "frbr_uri", "languages", "authority_score")
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
            request,
            _("Queued tasks to update extracted citations for %(count)d works.")
            % {"count": count},
        )

    update_extracted_citations.short_description = gettext_lazy(
        "Update extracted citations (background)"
    )

    def update_languages(self, request, queryset):
        with transaction.atomic():
            count = queryset.count()
            for work in queryset:
                work.update_languages()
        self.message_user(
            request, _("Updated languages for %(count)d works.") % {"count": count}
        )

    update_languages.short_description = gettext_lazy("Update languages")


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


@admin.register(CourtClass)
class CourtClassAdmin(admin.ModelAdmin):
    inlines = [EntityProfileInline]
    list_display = ("name", "slug")
    search_fields = ("name", "slug")


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    inlines = [EntityProfileInline]


@admin.register(Gazette)
class GazetteAdmin(ImportExportMixin, DocumentAdmin):
    resource_classes = [GazetteResource]
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


@admin.register(JournalArticle)
class JournalArticleAdmin(DocumentAdmin):
    pass


@admin.register(ExternalDocument)
class ExternalDocumentAdmin(DocumentAdmin):
    prepopulated_fields = {"frbr_uri_number": ("title",)}
    fieldsets = copy.deepcopy(DocumentAdmin.fieldsets)
    fieldsets[0][1]["fields"].extend(["nature"])

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


class UserFollowingInline(admin.TabularInline):
    model = UserFollowing
    extra = 0
    fields = (
        "__str__",
        "last_alerted_at",
    )
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class SavedSearchInline(admin.TabularInline):
    model = SavedSearch
    extra = 0
    fields = ("q", "a", "filters", "note", "last_alerted_at")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class UserAdminCustom(ImportExportMixin, UserAdmin):
    resource_classes = [UserResource]
    inlines = [UserFollowingInline, SavedSearchInline]
    actions = ["require_accept_terms"]

    def require_accept_terms(self, request, queryset):
        with transaction.atomic():
            count = queryset.count()
            UserProfile.objects.filter(user__in=queryset).update(accepted_terms_at=None)
        self.message_user(
            request,
            _("Set 'accepted terms of use' to False for %(count)d users.")
            % {"count": count},
        )

    require_accept_terms.short_description = gettext_lazy(
        "Require selected users to accept terms of use"
    )


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
    search_fields = ("name",)


@admin.register(Attorney)
class AttorneyAdmin(ImportExportMixin, admin.ModelAdmin):
    resource_classes = [AttorneyResource]
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
    resource_classes = [RatificationResource]
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
        AttachedFileNature,
        CaseAction,
        CitationLink,
        CitationProcessing,
        CourtDivision,
        CustomPropertyLabel,
        DocumentAccessGroup,
        Treatment,
        ProvisionEnrichment,
        UncommencedProvision,
        UnconstitutionalProvision,
    ]
)
admin.site.unregister(User)
admin.site.register(User, UserAdminCustom)

admin.site.site_header = settings.PEACHJAM["APP_NAME"]
