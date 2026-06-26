from urllib.parse import urlencode

from django.contrib import admin, messages
from django.contrib.admin.utils import quote
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.html import format_html
from django.utils.translation import gettext_lazy
from django.views.generic import TemplateView

from peachjam.analysis.judges import judge_identity_service
from peachjam.forms import JudgeIdentityWorkflowForm
from peachjam.models import Bench, Judge, JudgeAlias, JudgePerson


class JudgeIdentityWorkflowMixin:
    model = JudgePerson
    workflow_limit = 200
    template_name = "admin/peachjam/judge_identity/workflow_change_form.html"
    alias_tab = "aliases"
    judge_people_tab = "judge_people"

    def get_workflow_initial(self, request):
        initial = {}
        judge_person_id = request.GET.get("judge_person")
        if judge_person_id:
            initial["target_judge_person"] = judge_person_id
            initial["merge_target_judge_person"] = judge_person_id
        return initial

    def get_active_tab(
        self,
        request,
        selected_alias_ids,
        selected_judge_person_ids,
        form=None,
    ):
        requested_tab = (
            request.POST.get("tab") or request.GET.get("tab") or ""
        ).strip()
        if requested_tab in {self.alias_tab, self.judge_people_tab}:
            active_tab = requested_tab
        elif selected_judge_person_ids and not selected_alias_ids:
            active_tab = self.judge_people_tab
        else:
            active_tab = self.alias_tab

        if form is None or not form.errors:
            return active_tab

        if form["selected_aliases"].errors:
            return self.alias_tab
        if (
            form["selected_judge_people"].errors
            or form["merge_target_judge_person"].errors
        ):
            return self.judge_people_tab
        return active_tab

    def get_alias_workflow_rows(self, query):
        alias_qs = JudgeAlias.objects.select_related("judge_person").order_by(
            "name",
            "pk",
        )
        if query:
            alias_qs = alias_qs.filter(
                Q(name__icontains=query)
                | Q(title__icontains=query)
                | Q(normalized_name__icontains=query)
                | Q(judge_person__full_name__icontains=query)
            ).distinct()

        aliases = list(alias_qs[: self.workflow_limit])
        alias_ids = [alias.pk for alias in aliases]
        alias_names = [alias.name for alias in aliases]

        alias_duplicates = {
            row["name"]: row["count"]
            for row in JudgeAlias.objects.filter(name__in=alias_names)
            .values("name")
            .annotate(count=Count("pk"))
        }
        legacy_judges = {
            judge.name: judge
            for judge in Judge.objects.filter(name__in=alias_names).order_by("pk")
        }

        bench_stats = {
            row["matched_alias_id"]: row
            for row in Bench.objects.filter(matched_alias_id__in=alias_ids)
            .values("matched_alias_id")
            .annotate(
                bench_rows=Count("pk"),
                judgments=Count("judgment_id", distinct=True),
            )
        }

        rows = []
        for alias in aliases:
            stats = bench_stats.get(alias.pk, {})
            legacy_judge = legacy_judges.get(alias.name)

            if alias_duplicates.get(alias.name, 0) > 1:
                status = "Conflict"
                status_class = "warning"
            elif stats.get("bench_rows", 0):
                status = "Mapped"
                status_class = "success"
            elif legacy_judge is not None:
                status = "Alias only"
                status_class = "info"
            else:
                status = "Orphan"
                status_class = "secondary"

            notes = []
            if alias_duplicates.get(alias.name, 0) > 1:
                notes.append(
                    gettext_lazy(
                        "{} alias records currently share this exact name."
                    ).format(alias_duplicates[alias.name])
                )
            if legacy_judge is None:
                notes.append(
                    gettext_lazy(
                        "No matching legacy Judge row exists for this alias name."
                    )
                )

            rows.append(
                {
                    "alias": alias,
                    "legacy_judge": legacy_judge,
                    "current_person": alias.judge_person,
                    "status": status,
                    "status_class": status_class,
                    "bench_rows": stats.get("bench_rows", 0),
                    "judgments": stats.get("judgments", 0),
                    "notes": notes,
                }
            )

        return rows

    def get_judge_person_workflow_rows(self, query):
        judge_person_qs = JudgePerson.objects.order_by("full_name", "pk").annotate(
            alias_count=Count("aliases", distinct=True),
            bench_rows=Count("bench_entries", distinct=True),
            judgments=Count("bench_entries__judgment_id", distinct=True),
        )
        if query:
            judge_person_qs = judge_person_qs.filter(
                Q(full_name__icontains=query) | Q(aliases__name__icontains=query)
            ).distinct()

        rows = []
        for judge_person in judge_person_qs[: self.workflow_limit]:
            if judge_person.alias_count == 0 and judge_person.bench_rows == 0:
                status = "Empty"
                status_class = "secondary"
            elif judge_person.alias_count == 0:
                status = "Conflict"
                status_class = "warning"
            elif judge_person.bench_rows == 0:
                status = "Alias only"
                status_class = "info"
            else:
                status = "In use"
                status_class = "success"

            notes = []
            if judge_person.alias_count == 0 and judge_person.bench_rows:
                notes.append(
                    gettext_lazy(
                        "Bench rows still point here, but this judge person has no aliases."
                    )
                )
            if judge_person.alias_count and judge_person.bench_rows == 0:
                notes.append(
                    gettext_lazy("This judge person currently owns aliases only.")
                )

            rows.append(
                {
                    "judge_person": judge_person,
                    "alias_count": judge_person.alias_count,
                    "bench_rows": judge_person.bench_rows,
                    "judgments": judge_person.judgments,
                    "status": status,
                    "status_class": status_class,
                    "notes": notes,
                }
            )

        return rows

    def apply_workflow(self, cleaned_data):
        action = cleaned_data["action"]
        handlers = {
            JudgeIdentityWorkflowForm.APPLY_IDENTITY_CHANGES: self.apply_identity_changes,
            JudgeIdentityWorkflowForm.MERGE_JUDGE_PEOPLE: self.merge_selected_judge_people,
            JudgeIdentityWorkflowForm.DELETE_RECORDS: self.delete_selected_records,
        }
        try:
            return handlers[action](cleaned_data)
        except KeyError as exc:
            raise ValidationError(gettext_lazy("Choose a workflow action.")) from exc

    def apply_identity_changes(self, cleaned_data):
        with transaction.atomic():
            selected_aliases = list(cleaned_data["selected_aliases"])
            judge_person = cleaned_data["target_judge_person"]
            requested_name = cleaned_data["target_full_name"]
            created = False
            renamed = False
            old_name = None
            if judge_person is None:
                judge_person, created = (
                    judge_identity_service.get_or_create_judge_person(requested_name)
                )

            source_judge_people = set()
            moved_count = len(selected_aliases)
            if selected_aliases:
                source_judge_people = {
                    judge_alias.judge_person
                    for judge_alias in selected_aliases
                    if judge_alias.judge_person_id
                    and judge_alias.judge_person_id != judge_person.pk
                }
                for judge_alias in selected_aliases:
                    judge_identity_service.move_judge_alias_to_person(
                        judge_alias, judge_person
                    )

            if requested_name and judge_person.full_name != requested_name:
                old_name = judge_person.full_name
                judge_identity_service.rename_judge_person(judge_person, requested_name)
                renamed = True

            deleted_count = 0
            for source_judge_person in source_judge_people:
                source_judge_person.refresh_from_db()
                if (
                    not source_judge_person.aliases.exists()
                    and not source_judge_person.bench_entries.exists()
                ):
                    source_judge_person.delete()
                    deleted_count += 1

        return {
            "action": JudgeIdentityWorkflowForm.APPLY_IDENTITY_CHANGES,
            "judge_person": judge_person,
            "created": created,
            "renamed": renamed,
            "old_name": old_name,
            "count": moved_count,
            "deleted_count": deleted_count,
        }

    def merge_selected_judge_people(self, cleaned_data):
        with transaction.atomic():
            judge_person = cleaned_data["merge_target_judge_person"]
            duplicates = [
                candidate
                for candidate in cleaned_data["selected_judge_people"]
                if candidate.pk != judge_person.pk
            ]
            judge_identity_service.merge_judge_people(judge_person, duplicates)

        return {
            "action": JudgeIdentityWorkflowForm.MERGE_JUDGE_PEOPLE,
            "judge_person": judge_person,
            "count": len(duplicates),
        }

    def delete_selected_records(self, cleaned_data):
        with transaction.atomic():
            delete_mode = cleaned_data.get("delete_mode") or "aliases"
            selected_aliases = list(cleaned_data["selected_aliases"])
            selected_judge_people = list(cleaned_data["selected_judge_people"])
            selected_judge_person_ids = {
                judge_person.pk for judge_person in selected_judge_people
            }
            selected_alias_count = 0
            judge_people_result = {
                "judge_person_count": 0,
                "alias_count": 0,
                "cleared_matched_alias_count": 0,
                "cleared_judge_person_count": 0,
            }

            if delete_mode in {"aliases", "both"}:
                if delete_mode == "both":
                    selected_aliases = [
                        judge_alias
                        for judge_alias in selected_aliases
                        if judge_alias.judge_person_id not in selected_judge_person_ids
                    ]
                alias_result = judge_identity_service.delete_judge_aliases(
                    selected_aliases
                )
                selected_alias_count = alias_result["alias_count"]
            else:
                alias_result = {
                    "alias_count": 0,
                    "cleared_matched_alias_count": 0,
                }

            if delete_mode in {"judge_people", "both"}:
                judge_people_result = judge_identity_service.delete_judge_people(
                    selected_judge_people
                )

        return {
            "action": JudgeIdentityWorkflowForm.DELETE_RECORDS,
            "judge_person": None,
            "alias_count": selected_alias_count + judge_people_result["alias_count"],
            "judge_person_count": judge_people_result["judge_person_count"],
            "cleared_matched_alias_count": (
                alias_result["cleared_matched_alias_count"]
                + judge_people_result["cleared_matched_alias_count"]
            ),
            "cleared_judge_person_count": judge_people_result[
                "cleared_judge_person_count"
            ],
        }

    def build_workflow_success_message(self, result):
        action = result["action"]
        judge_person = result.get("judge_person")

        if action == JudgeIdentityWorkflowForm.APPLY_IDENTITY_CHANGES:
            change_url = reverse(
                "admin:peachjam_judgeperson_change",
                args=[quote(judge_person.pk)],
            )
            if result["count"] == 0 and result["renamed"]:
                return format_html(
                    'Renamed judge person "{}" to <a href="{}">{}</a>.',
                    result["old_name"],
                    change_url,
                    judge_person.full_name,
                )
            if result["count"] == 0:
                return gettext_lazy("No judge identity changes were applied.")

            action_label = (
                gettext_lazy("Created judge person")
                if result["created"]
                else gettext_lazy("Updated judge person")
            )
            summary = gettext_lazy(
                "Moved {} selected aliases to this judge person, refreshed their "
                "bench links automatically, and deleted {} now-empty source judge "
                "people."
            )
            if result["renamed"]:
                return format_html(
                    '{} <a href="{}">{}</a>. Moved {} selected aliases to this '
                    "judge person, refreshed their bench links automatically, "
                    "deleted {} now-empty source judge people, and renamed the "
                    'judge person from "{}".',
                    action_label,
                    change_url,
                    judge_person.full_name,
                    result["count"],
                    result["deleted_count"],
                    result["old_name"],
                )
            summary = summary.format(result["count"], result["deleted_count"])
            return format_html(
                '{} <a href="{}">{}</a>. {}',
                action_label,
                change_url,
                judge_person.full_name,
                summary,
            )

        if action == JudgeIdentityWorkflowForm.MERGE_JUDGE_PEOPLE:
            change_url = reverse(
                "admin:peachjam_judgeperson_change",
                args=[quote(judge_person.pk)],
            )
            return format_html(
                'Merged {} selected judge people into <a href="{}">{}</a>.',
                result["count"],
                change_url,
                judge_person.full_name,
            )

        if action == JudgeIdentityWorkflowForm.DELETE_RECORDS:
            message_bits = []
            if result["alias_count"]:
                message_bits.append(
                    gettext_lazy("Deleted {} aliases").format(result["alias_count"])
                )
            if result["judge_person_count"]:
                message_bits.append(
                    gettext_lazy("Deleted {} judge people").format(
                        result["judge_person_count"]
                    )
                )
            if result["cleared_matched_alias_count"]:
                message_bits.append(
                    gettext_lazy("Cleared {} matched alias links on bench rows").format(
                        result["cleared_matched_alias_count"]
                    )
                )
            if result["cleared_judge_person_count"]:
                message_bits.append(
                    gettext_lazy("Cleared {} judge person links on bench rows").format(
                        result["cleared_judge_person_count"]
                    )
                )
            if not message_bits:
                message_bits.append(gettext_lazy("No records were deleted"))
            return " ".join(f"{message}." for message in message_bits)

        return gettext_lazy("Judge identity workflow completed.")


@method_decorator(staff_member_required, name="dispatch")
class JudgeIdentityWorkflowView(JudgeIdentityWorkflowMixin, TemplateView):
    def dispatch(self, request, *args, **kwargs):
        if not JudgePerson.canonical_identity_enabled() or not request.user.has_perm(
            "peachjam.change_judgeperson"
        ):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        return self.render_workflow(request)

    def post(self, request, *args, **kwargs):
        return self.render_workflow(request)

    def render_workflow(self, request):
        query = (request.GET.get("q") or request.POST.get("q") or "").strip()
        selected_alias_ids = request.POST.getlist("selected_aliases")
        selected_judge_person_ids = request.POST.getlist("selected_judge_people")

        if not selected_judge_person_ids and request.GET.get("judge_person"):
            selected_judge_person_ids = [request.GET["judge_person"]]

        if request.method == "POST":
            form = JudgeIdentityWorkflowForm(request.POST)
            if form.is_valid():
                result = self.apply_workflow(form.cleaned_data)
                messages.success(
                    request,
                    self.build_workflow_success_message(result),
                )
                redirect_url = reverse("peachjam_judgeperson_workflow")
                params = {}
                if query:
                    params["q"] = query
                active_tab = self.get_active_tab(
                    request,
                    selected_alias_ids,
                    selected_judge_person_ids,
                )
                if active_tab != self.alias_tab:
                    params["tab"] = active_tab
                if result.get("judge_person") is not None:
                    params["judge_person"] = result["judge_person"].pk
                query_string = f"?{urlencode(params)}" if params else ""
                return HttpResponseRedirect(f"{redirect_url}{query_string}")
        else:
            form = JudgeIdentityWorkflowForm(initial=self.get_workflow_initial(request))

        active_tab = self.get_active_tab(
            request,
            selected_alias_ids,
            selected_judge_person_ids,
            form=form,
        )
        alias_workflow_rows = self.get_alias_workflow_rows(query)
        judge_person_workflow_rows = self.get_judge_person_workflow_rows(query)
        context = {
            **admin.site.each_context(request),
            "opts": self.model._meta,
            "title": gettext_lazy("Judge identity workflow"),
            "subtitle": None,
            "form": form,
            "media": form.media,
            "query": query,
            "selected_alias_ids": selected_alias_ids,
            "selected_judge_person_ids": selected_judge_person_ids,
            "alias_workflow_rows": alias_workflow_rows,
            "judge_person_workflow_rows": judge_person_workflow_rows,
            "workflow_limit": self.workflow_limit,
            "active_tab": active_tab,
            "alias_tab": self.alias_tab,
            "judge_people_tab": self.judge_people_tab,
        }
        return TemplateResponse(request, self.template_name, context)
