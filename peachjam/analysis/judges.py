import re
import unicodedata

from django.db import transaction
from django.db.models import Count, Q
from django.utils.text import slugify

TITLE_TOKENS = {
    "ACJ",
    "ACTJ",
    "AJ",
    "AJP",
    "AJA",
    "AP",
    "CJ",
    "CM",
    "DCJ",
    "J",
    "JA",
    "JCC",
    "JP",
    "PM",
    "P",
    "R",
    "SCJ",
    "SCM",
}

PUNCTUATION_PATTERN = re.compile(r"[.,;:()]+")
WHITESPACE_PATTERN = re.compile(r"\s+")
NON_ALNUM_PATTERN = re.compile(r"[^0-9A-Za-z]+")


class JudgeIdentityService:
    def normalize_judge_name(self, value):
        value = unicodedata.normalize("NFKC", value or "")
        value = value.strip()
        value = value.replace(".", "")
        value = PUNCTUATION_PATTERN.sub(" ", value)
        value = value.replace("-", " ")
        value = NON_ALNUM_PATTERN.sub(" ", value)
        value = WHITESPACE_PATTERN.sub(" ", value)
        return value.casefold().strip()

    def parse_judge_name(self, value):
        """Split a source judge string into raw, normalized, canonical, and title parts."""
        raw_name = (value or "").strip()
        normalized_name = self.normalize_judge_name(raw_name)
        tokens = normalized_name.split()
        title = ""
        if tokens:
            candidate_title = tokens[-1].upper()
            if candidate_title in TITLE_TOKENS:
                title = candidate_title
                tokens = tokens[:-1]

        return {
            "raw_name": raw_name,
            "normalized_name": normalized_name,
            "base_name": " ".join(tokens).strip(),
            "title": title,
        }

    def canonical_name_from_aliases(self, names):
        candidates = []
        for name in names:
            parts = self.parse_judge_name(name)
            base_name = parts["base_name"] or parts["normalized_name"]
            if not base_name:
                continue

            words = re.split(r"\s+", (name or "").strip())
            if parts["title"] and words:
                words = words[:-1]
            display_name = " ".join(words).strip(" ,.;:-")
            candidates.append(display_name or (name or "").strip())

        if not candidates:
            return "judge"

        return sorted(candidates, key=lambda value: (-len(value), value.casefold()))[0]

    def unique_judge_slug(self, model, name, *, pk=None):
        base_slug = slugify(name) or "judge"
        slug = base_slug
        suffix = 2
        while True:
            qs = model.objects.filter(slug=slug)
            if pk:
                qs = qs.exclude(pk=pk)
            if not qs.exists():
                return slug
            slug = f"{base_slug}-{suffix}"
            suffix += 1

    def get_or_create_judge_person(self, full_name):
        from peachjam.models import JudgePerson

        full_name = (full_name or "").strip() or "judge"
        existing_person = (
            JudgePerson.objects.filter(full_name__iexact=full_name)
            .order_by("pk")
            .first()
        )
        if existing_person is not None:
            return existing_person, False

        return (
            JudgePerson.objects.create(
                full_name=full_name,
                slug=self.unique_judge_slug(JudgePerson, full_name),
            ),
            True,
        )

    def rename_judge_person(self, judge_person, full_name):
        full_name = (full_name or "").strip()
        if not full_name:
            return judge_person

        judge_person.full_name = full_name
        judge_person.slug = self.unique_judge_slug(
            judge_person.__class__,
            full_name,
            pk=judge_person.pk,
        )
        judge_person.save(update_fields=["full_name", "slug"])
        return judge_person

    def ensure_judge_alias(self, judge_person, name):
        from peachjam.models import JudgeAlias

        alias = (
            JudgeAlias.objects.filter(judge_person=judge_person, name=name)
            .order_by("pk")
            .first()
        )
        normalized_name = self.normalize_judge_name(name)
        if alias is not None:
            if alias.normalized_name != normalized_name:
                alias.normalized_name = normalized_name
                alias.save(update_fields=["normalized_name"])
            return alias, False

        return (
            JudgeAlias.objects.create(
                judge_person=judge_person,
                name=name,
                normalized_name=normalized_name,
            ),
            True,
        )

    def update_bench_rows(self, queryset, judge_person, matched_alias, source_name):
        title = self.parse_judge_name(source_name)["title"]
        updated_count = 0

        for bench in queryset:
            update_fields = []

            if judge_person is not None and bench.judge_person_id != judge_person.pk:
                bench.judge_person = judge_person
                update_fields.append("judge_person")

            if matched_alias is not None and bench.matched_alias_id != matched_alias.pk:
                bench.matched_alias = matched_alias
                update_fields.append("matched_alias")

            if not bench.is_manual_override or not bench.extracted_name:
                if bench.extracted_name != source_name:
                    bench.extracted_name = source_name
                    update_fields.append("extracted_name")

            if not bench.is_manual_override or not bench.title:
                if bench.title != title:
                    bench.title = title
                    update_fields.append("title")

            if update_fields:
                bench.save(update_fields=update_fields)
                updated_count += 1

        return updated_count

    def assign_legacy_judge_to_person(
        self, legacy_judge, judge_person, alias_name=None
    ):
        from peachjam.models import Bench

        source_name = alias_name or legacy_judge.name
        judge_alias, created = self.ensure_judge_alias(judge_person, source_name)
        benches = Bench.objects.filter(judge=legacy_judge).order_by("pk")
        self.update_bench_rows(benches, judge_person, judge_alias, source_name)
        return judge_alias, created

    def dedupe_judge_aliases(self, judge_person):
        from peachjam.models import Bench, JudgeAlias

        duplicate_names = (
            JudgeAlias.objects.filter(judge_person=judge_person)
            .values("name")
            .annotate(count=Count("pk"))
            .filter(count__gt=1)
        )

        for row in duplicate_names:
            aliases = list(
                JudgeAlias.objects.filter(judge_person=judge_person, name=row["name"])
                .order_by("pk")
                .all()
            )
            primary_alias = aliases[0]
            duplicate_aliases = aliases[1:]
            duplicate_ids = [alias.pk for alias in duplicate_aliases]
            if duplicate_ids:
                Bench.objects.filter(matched_alias_id__in=duplicate_ids).update(
                    matched_alias=primary_alias
                )
                JudgeAlias.objects.filter(pk__in=duplicate_ids).delete()

        return judge_person

    def move_judge_alias_to_person(self, judge_alias, judge_person):
        from peachjam.models import Bench, Judge

        source_name = judge_alias.name
        target_alias, created = self.ensure_judge_alias(judge_person, source_name)

        if target_alias.pk != judge_alias.pk:
            bench_qs = Bench.objects.filter(
                Q(matched_alias=judge_alias) | Q(judge__name=source_name)
            ).order_by("pk")
            self.update_bench_rows(bench_qs, judge_person, target_alias, source_name)
            judge_alias.delete()
            return target_alias, created

        if judge_alias.judge_person_id != judge_person.pk:
            judge_alias.judge_person = judge_person
            judge_alias.save(update_fields=["judge_person"])

        legacy_judge = Judge.objects.filter(name=source_name).order_by("pk").first()
        if legacy_judge is not None:
            self.assign_legacy_judge_to_person(
                legacy_judge,
                judge_person,
                alias_name=source_name,
            )
        else:
            bench_qs = Bench.objects.filter(matched_alias=judge_alias).order_by("pk")
            self.update_bench_rows(bench_qs, judge_person, judge_alias, source_name)

        self.dedupe_judge_aliases(judge_person)
        return judge_alias, created

    def merge_judge_people(self, primary_judge_person, duplicate_judge_people):
        from peachjam.models import Bench

        duplicate_judge_people = [
            duplicate
            for duplicate in duplicate_judge_people
            if duplicate.pk and duplicate.pk != primary_judge_person.pk
        ]
        if not duplicate_judge_people:
            return primary_judge_person

        with transaction.atomic():
            for duplicate in duplicate_judge_people:
                aliases = list(duplicate.aliases.order_by("pk"))
                for judge_alias in aliases:
                    self.move_judge_alias_to_person(judge_alias, primary_judge_person)

                Bench.objects.filter(judge_person=duplicate).update(
                    judge_person=primary_judge_person
                )
                duplicate.delete()

            self.dedupe_judge_aliases(primary_judge_person)

        return primary_judge_person

    def delete_judge_aliases(self, judge_aliases):
        from peachjam.models import Bench, JudgeAlias

        alias_ids = list(
            {judge_alias.pk for judge_alias in judge_aliases if judge_alias.pk}
        )
        if not alias_ids:
            return {
                "alias_count": 0,
                "cleared_matched_alias_count": 0,
            }

        cleared_matched_alias_count = Bench.objects.filter(
            matched_alias_id__in=alias_ids
        ).update(matched_alias=None)
        alias_count = JudgeAlias.objects.filter(pk__in=alias_ids).count()
        JudgeAlias.objects.filter(pk__in=alias_ids).delete()

        return {
            "alias_count": alias_count,
            "cleared_matched_alias_count": cleared_matched_alias_count,
        }

    def delete_judge_people(self, judge_people):
        from peachjam.models import Bench, JudgeAlias, JudgePerson

        judge_person_ids = [
            judge_person.pk
            for judge_person in judge_people
            if judge_person.pk is not None
        ]
        if not judge_person_ids:
            return {
                "judge_person_count": 0,
                "alias_count": 0,
                "cleared_matched_alias_count": 0,
                "cleared_judge_person_count": 0,
            }

        cleared_matched_alias_count = Bench.objects.filter(
            matched_alias__judge_person_id__in=judge_person_ids
        ).update(matched_alias=None)
        cleared_judge_person_count = Bench.objects.filter(
            judge_person_id__in=judge_person_ids
        ).update(judge_person=None)
        alias_count = JudgeAlias.objects.filter(
            judge_person_id__in=judge_person_ids
        ).count()
        judge_person_count = JudgePerson.objects.filter(pk__in=judge_person_ids).count()
        JudgePerson.objects.filter(pk__in=judge_person_ids).delete()

        return {
            "judge_person_count": judge_person_count,
            "alias_count": alias_count,
            "cleared_matched_alias_count": cleared_matched_alias_count,
            "cleared_judge_person_count": cleared_judge_person_count,
        }


judge_identity_service = JudgeIdentityService()
