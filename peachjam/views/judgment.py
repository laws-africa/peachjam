from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.safestring import mark_safe
from django.utils.text import gettext_lazy as _
from django.utils.timezone import now
from django.views.decorators.cache import never_cache
from django.views.generic import DetailView, TemplateView

from peachjam.helpers import add_slash_to_frbr_uri
from peachjam.models import CourtClass, Judgment
from peachjam.models.settings import pj_settings
from peachjam.models.taxonomies import DocumentTopic
from peachjam.registry import registry
from peachjam.views.generic_views import BaseDocumentDetailView
from peachjam_subs.mixins import SubscriptionRequiredMixin


class JudgmentListView(TemplateView):
    template_name = "peachjam/judgment_list.html"
    navbar_link = "judgments"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["recent_judgments"] = (
            Judgment.objects.for_document_table()
            .exclude(published=False)
            .order_by("-date")[:30]
        )
        context["nature"] = "Judgment"
        context["doc_count"] = Judgment.objects.filter(published=True).count()
        context["doc_count_noun"] = _("judgment")
        context["doc_count_noun_plural"] = _("judgments")
        context["help_link"] = "judgments/courts"
        self.add_entity_profile(context)
        self.get_court_classes(context)
        return context

    def get_court_classes(self, context):
        context["court_classes"] = CourtClass.objects.prefetch_related("courts")

    def add_entity_profile(self, context):
        pass


class FlynoteTopicListView(TemplateView):
    template_name = "peachjam/flynote_topic_list.html"

    def get(self, request, *args, **kwargs):
        root = pj_settings().flynote_taxonomy_root
        if not root:
            return redirect(reverse("judgment_list"))
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        root = pj_settings().flynote_taxonomy_root

        children = root.get_children()
        topics = []
        for child in children:
            descendant_ids = list(child.get_descendants().values_list("pk", flat=True))
            descendant_ids.append(child.pk)
            count = (
                DocumentTopic.objects.filter(topic_id__in=descendant_ids)
                .values("document_id")
                .distinct()
                .count()
            )
            child_names = list(child.get_children().values_list("name", flat=True)[:3])
            topics.append({"topic": child, "count": count, "child_names": child_names})

        # popular: top 12 by count; all: full list alphabetically
        sorted_by_count = sorted(topics, key=lambda x: x["count"], reverse=True)
        context["popular_topics"] = sorted_by_count[:12]

        all_topics_sorted = sorted(topics, key=lambda x: x["topic"].name)
        q = self.request.GET.get("q", "").strip()
        if q:
            all_topics_sorted = [
                t for t in all_topics_sorted if q.lower() in t["topic"].name.lower()
            ]

        context["all_topics"] = all_topics_sorted
        context["total_judgment_count"] = sum(t["count"] for t in topics)
        context["root"] = root
        return context


@registry.register_doc_type("judgment")
class JudgmentDetailView(BaseDocumentDetailView):
    model = Judgment
    template_name = "peachjam/judgment_detail.html"

    def get_notices(self):
        notices = super().get_notices()
        document = self.get_object()
        if document.anonymised:
            notices.append(
                {
                    "type": messages.INFO,
                    "html": mark_safe(
                        _(
                            "This judgment has been anonymised to protect personal "
                            "information in compliance with the law."
                        )
                    ),
                }
            )
        return notices

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["judges"] = [
            bench.judge
            for bench in self.get_object().bench.select_related("judge").all()
        ]
        return context

    def get_taxonomy_queryset(self):
        qs = super().get_taxonomy_queryset()
        settings = pj_settings()
        root = settings.flynote_taxonomy_root
        if root:
            flynote_pks = set(root.get_descendants().values_list("pk", flat=True))
            flynote_pks.add(root.pk)
            qs = qs.exclude(pk__in=flynote_pks)
        return qs

    def add_flynote_taxonomies(self, context):
        settings = pj_settings()
        root = settings.flynote_taxonomy_root
        if not root:
            return

        doc = self.object
        all_topic_ids = set(doc.taxonomies.values_list("topic__pk", flat=True))
        flynote_topics = root.get_descendants().filter(pk__in=all_topic_ids)

        if not flynote_topics.exists():
            return

        context["flynote_taxonomies"] = flynote_topics
        context["flynote_root"] = root


@method_decorator(never_cache, name="dispatch")
class ReviewFlynoteMappingView(TemplateView):
    """Web-based UI for cleaning duplicate flynote taxonomy topics.

    The generate action runs the LLM in a background thread and writes progress
    to /tmp/flynote_progress.json which the frontend polls via AJAX.
    """

    template_name = "peachjam/review_flynote_mapping.html"
    PROPOSALS_FILE = "/tmp/flynote_proposals.json"
    PROGRESS_FILE = "/tmp/flynote_progress.json"

    @staticmethod
    def _read_json(path):
        import json

        try:
            with open(path) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    @staticmethod
    def _write_json(path, data):
        import json

        with open(path, "w") as f:
            json.dump(data, f, ensure_ascii=False)

    def get_context_data(self, **kwargs):
        import json

        from peachjam.models.settings import pj_settings

        context = super().get_context_data(**kwargs)
        proposals = self._read_json(self.PROPOSALS_FILE) or []
        context["proposals"] = json.dumps(proposals)
        context["is_running"] = self._is_running()

        root = pj_settings().flynote_taxonomy_root
        if root:
            all_topics = list(
                root.get_descendants().order_by("name").values_list("id", "name")
            )
        else:
            all_topics = []
        context["all_topics_json"] = json.dumps(
            [{"id": t_id, "name": name} for t_id, name in all_topics]
        )
        return context

    def _is_running(self):
        import os
        import time

        progress = self._read_json(self.PROGRESS_FILE)
        if not progress or progress.get("status") != "running":
            return False
        try:
            mtime = os.path.getmtime(self.PROGRESS_FILE)
            if time.time() - mtime > 300:
                self._write_json(
                    self.PROGRESS_FILE,
                    {
                        "status": "error",
                        "activities": [{"type": "error", "text": "Process timed out."}],
                    },
                )
                return False
        except OSError:
            return False
        return True

    MERGE_PROGRESS_FILE = "/tmp/flynote_merge_progress.json"

    def post(self, request, *args, **kwargs):
        import json

        from django.http import JsonResponse

        content_type = request.content_type or ""

        if "application/json" in content_type:
            try:
                body = json.loads(request.body)
            except (json.JSONDecodeError, ValueError):
                return JsonResponse({"error": "Invalid JSON"}, status=400)
            action = body.get("action", "")
            if action == "save":
                return self._handle_save(request, body)
            if action == "apply":
                return self._handle_apply(request, body)
            return JsonResponse({"error": "Unknown action"}, status=400)

        action = request.POST.get("action", "")
        if action == "generate":
            return self._handle_generate(request)
        if action == "cancel":
            return self._handle_cancel(request)

        return redirect(request.path)

    def _handle_generate(self, request):
        """Start the LLM processing in a background thread."""
        import threading

        if self._is_running():
            return redirect(request.path)

        limit = int(request.POST.get("limit", 0) or 0)

        self._write_json(
            self.PROGRESS_FILE,
            {
                "status": "running",
                "batch": 0,
                "total_batches": 0,
                "percent": 0,
                "activities": [{"type": "info", "text": "Starting AI cleaning..."}],
                "groups_found": 0,
            },
        )
        self._write_json(self.PROPOSALS_FILE, [])

        thread = threading.Thread(
            target=self._run_generation_static,
            args=(self.PROPOSALS_FILE, self.PROGRESS_FILE, limit),
            daemon=True,
        )
        thread.start()
        return redirect(request.path)

    def _handle_cancel(self, request):
        """Cancel a running scan by writing cancelled status."""
        from django.http import JsonResponse

        self._write_json(
            self.PROGRESS_FILE,
            {
                "status": "cancelled",
                "activities": [{"type": "info", "text": "Scan cancelled by user."}],
            },
        )
        return JsonResponse({"ok": True})

    @staticmethod
    def _run_generation_static(proposals_file, progress_file, limit=0):
        """Background thread: run the LLM mapper with progress updates."""
        import json

        from peachjam_ml.flynote_mapper import FlynoteLLMMapper

        class ScanCancelled(Exception):
            pass

        all_groups = []

        def write_prog(data):
            with open(progress_file, "w") as f:
                json.dump(data, f, ensure_ascii=False)

        def is_cancelled():
            try:
                with open(progress_file) as f:
                    data = json.load(f)
                return data.get("status") == "cancelled"
            except (FileNotFoundError, json.JSONDecodeError):
                return False

        def on_progress(
            batch_num,
            total_batches,
            batch_topics,
            found_groups,
            phase="Processing",
        ):
            if is_cancelled():
                raise ScanCancelled()

            pct = int((batch_num / total_batches) * 100) if total_batches else 0

            activities = []
            if batch_topics:
                sample = [t["name"] for t in batch_topics[:4]]
                activities.append(
                    {
                        "type": "scan",
                        "text": (
                            f"[{phase}] Step {batch_num}/{total_batches}: "
                            f'Scanning "{sample[0]}" ... "{sample[-1]}"'
                        ),
                    }
                )
            for g in found_groups:
                dup_names = [
                    d["name"] for d in g.get("duplicates", []) if d.get("name")
                ]
                if dup_names:
                    activities.append(
                        {
                            "type": "found",
                            "text": (
                                f"Duplicates: {', '.join(dup_names[:5])} "
                                f'\u2192 "{g.get("canonical", "?")}"'
                            ),
                        }
                    )

            write_prog(
                {
                    "status": "running",
                    "batch": batch_num,
                    "total_batches": total_batches,
                    "percent": pct,
                    "phase": phase,
                    "activities": activities,
                    "groups_found": len(all_groups),
                }
            )

        try:
            mapper = FlynoteLLMMapper()
            result = mapper.find_all_duplicates(
                progress_callback=on_progress,
                limit=limit or None,
            )

            with open(proposals_file, "w") as f:
                json.dump(result, f, ensure_ascii=False)

            write_prog(
                {
                    "status": "done",
                    "percent": 100,
                    "activities": [
                        {
                            "type": "info",
                            "text": f"Done! Found {len(result)} duplicate group(s).",
                        }
                    ],
                    "groups_found": len(result),
                }
            )
        except ScanCancelled:
            write_prog(
                {
                    "status": "cancelled",
                    "activities": [{"type": "info", "text": "Scan cancelled."}],
                }
            )
        except Exception as e:
            write_prog(
                {
                    "status": "error",
                    "percent": 0,
                    "activities": [{"type": "error", "text": f"Error: {str(e)}"}],
                    "groups_found": 0,
                }
            )

    def _handle_save(self, request, body):
        """Save edited proposals (from drag-and-drop / rename)."""
        from django.http import JsonResponse

        proposals = body.get("proposals", [])
        self._write_json(self.PROPOSALS_FILE, proposals)
        return JsonResponse({"ok": True})

    def _handle_apply(self, request, body):
        """Merge duplicate topics with progress tracking."""
        import threading

        from django.http import JsonResponse

        proposals = body.get("proposals", [])
        if not proposals:
            proposals = self._read_json(self.PROPOSALS_FILE) or []
        if not proposals:
            return JsonResponse({"error": "No proposals to apply"}, status=400)

        self._write_json(self.PROPOSALS_FILE, proposals)
        self._write_json(
            self.MERGE_PROGRESS_FILE,
            {"status": "running", "current": 0, "total": len(proposals), "merged": 0},
        )

        thread = threading.Thread(
            target=self._run_merge_static,
            args=(self.PROPOSALS_FILE, self.MERGE_PROGRESS_FILE),
            daemon=True,
        )
        thread.start()
        return JsonResponse({"ok": True, "total": len(proposals)})

    @staticmethod
    def _run_merge_static(proposals_file, merge_progress_file):
        """Background thread: merge duplicates with progress."""
        import json

        import django

        django.setup()
        from peachjam.models.taxonomies import DocumentTopic, Taxonomy

        def write_prog(data):
            with open(merge_progress_file, "w") as f:
                json.dump(data, f, ensure_ascii=False)

        try:
            with open(proposals_file) as f:
                proposals = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            proposals = []

        total = len(proposals)
        merged_count = 0

        for idx, group in enumerate(proposals):
            keep_id = group.get("keep_id")
            canonical_name = group.get("canonical", "")
            duplicate_ids = [
                d["id"] for d in group.get("duplicates", []) if d["id"] != keep_id
            ]
            is_rename_only = group.get("is_rename") and not duplicate_ids
            if not keep_id or (not duplicate_ids and not is_rename_only):
                write_prog(
                    {
                        "status": "running",
                        "current": idx + 1,
                        "total": total,
                        "merged": merged_count,
                        "current_group": canonical_name,
                    }
                )
                continue

            try:
                keep_topic = Taxonomy.objects.get(pk=keep_id)
                if canonical_name and keep_topic.name != canonical_name:
                    keep_topic.name = canonical_name
                    keep_topic.save()
            except Taxonomy.DoesNotExist:
                write_prog(
                    {
                        "status": "running",
                        "current": idx + 1,
                        "total": total,
                        "merged": merged_count,
                        "current_group": canonical_name,
                    }
                )
                continue

            for dup_id in duplicate_ids:
                DocumentTopic.objects.filter(topic_id=dup_id).exclude(
                    document_id__in=DocumentTopic.objects.filter(
                        topic_id=keep_id
                    ).values("document_id")
                ).update(topic_id=keep_id)
                DocumentTopic.objects.filter(topic_id=dup_id).delete()
                Taxonomy.objects.filter(pk=dup_id).delete()
                merged_count += 1

            write_prog(
                {
                    "status": "running",
                    "current": idx + 1,
                    "total": total,
                    "merged": merged_count,
                    "current_group": canonical_name,
                }
            )

        with open(proposals_file, "w") as f:
            json.dump([], f)

        write_prog(
            {
                "status": "done",
                "current": total,
                "total": total,
                "merged": merged_count,
            }
        )


class FlynoteMappingProgressView(TemplateView):
    """JSON endpoint polled by the progress modal.

    When the LLM is done, the response includes the full proposals so the
    frontend can render results without a page reload.
    """

    def get(self, request, *args, **kwargs):
        import json

        from django.http import JsonResponse

        try:
            with open("/tmp/flynote_progress.json") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {
                "status": "idle",
                "percent": 0,
                "activities": [],
                "groups_found": 0,
            }

        if data.get("status") == "done":
            try:
                with open("/tmp/flynote_proposals.json") as f:
                    data["proposals"] = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                data["proposals"] = []

        return JsonResponse(data)


class FlynoteMergeProgressView(TemplateView):
    """JSON endpoint polled by the merge progress modal."""

    def get(self, request, *args, **kwargs):
        import json

        from django.http import JsonResponse

        try:
            with open("/tmp/flynote_merge_progress.json") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {"status": "idle", "current": 0, "total": 0, "merged": 0}
        return JsonResponse(data)


@method_decorator(add_slash_to_frbr_uri(), name="setup")
@method_decorator(never_cache, name="dispatch")
class CaseHistoryView(SubscriptionRequiredMixin, DetailView):
    permission_required = "peachjam.can_view_case_history"
    model = Judgment
    slug_url_kwarg = "frbr_uri"
    slug_field = "expression_frbr_uri"
    template_name = "peachjam/_case_histories.html"

    def get_subscription_required_template(self):
        return self.template_name

    def add_case_histories(self, context):
        document = self.get_object()

        # judgments that impact this one
        histories = [
            {
                "document": ch.judgment_work.documents.first(),
                "children": [
                    {
                        "case_history": ch,
                        "document": document,
                    }
                ],
            }
            for ch in document.work.incoming_case_histories.select_related(
                "court", "historical_judgment_work", "outcome"
            )
            # ignore incoming history entries for dangling works that don't have a document
            if ch.judgment_work.documents.first()
        ]

        if histories:
            context["show_review_notice"] = True

        # judgments that this one impacts
        outgoing_histories = [
            {
                "case_history": ch,
                "document": ch.historical_judgment_work.documents.first()
                if ch.historical_judgment_work
                else None,
            }
            for ch in document.work.case_histories.select_related(
                "historical_judgment_work", "outcome"
            ).prefetch_related(
                "historical_judgment_work__documents",
                "historical_judgment_work__documents__outcomes",
                "historical_judgment_work__documents__court",
                "historical_judgment_work__documents__judges",
            )
        ]
        if outgoing_histories:
            histories.append(
                {
                    "document": document,
                    "children": outgoing_histories,
                }
            )

        today = now().date()
        for history in histories:
            for child in history["children"]:
                child["info"] = child["document"] or child["case_history"]

            # sort by date descending
            history["children"].sort(
                key=lambda x: x["info"].date or today, reverse=True
            )

        # sort by date descending
        histories.sort(key=lambda x: x["document"].date, reverse=True)

        context["case_histories"] = histories

        return histories

    def get_subscription_required_context(self):
        context = {}
        self.add_case_histories(context)
        return context

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_subscription_required_context())
        return context


@method_decorator(add_slash_to_frbr_uri(), name="setup")
@method_decorator(never_cache, name="dispatch")
class CaseSummaryView(SubscriptionRequiredMixin, DetailView):
    permission_required = "peachjam.can_view_document_summary"
    template_name = "peachjam/document/_judgment_summary.html"
    model = Judgment
    slug_url_kwarg = "frbr_uri"
    slug_field = "expression_frbr_uri"

    def has_permission(self):
        document = self.get_object()
        is_public = document.case_summary_public
        if is_public:
            return True
        return super().has_permission()

    def get_subscription_required_template(self):
        return self.template_name

    def get_subscription_required_context(self):
        context = {}
        document = self.get_object()
        if hasattr(document, "case_summary"):
            context = {"document": document}
        return context

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_subscription_required_context())
        return context
