import datetime
from io import StringIO
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from countries_plus.models import Country
from django.conf import settings
from django.contrib import admin
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from languages_plus.models import Language

from peachjam.admin import (
    BenchInline,
    BenchInlineForm,
    JudgmentAdmin,
    JudgmentForm,
    LegacyBenchInline,
)
from peachjam.analysis.judges import judge_identity_service
from peachjam.extractor import ExtractorError, ExtractorService
from peachjam.models import (
    Bench,
    Court,
    ExtractedCitation,
    Flynote,
    Judge,
    JudgeAlias,
    JudgePerson,
    Judgment,
    JudgmentFlynote,
)
from peachjam.views.judges import JudgePersonDetailView, split_judge_display_name

CANONICAL_JUDGE_IDENTITY_SETTINGS = {
    **settings.PEACHJAM,
    "CANONICAL_JUDGE_IDENTITY": True,
}
CANONICAL_JUDGE_IDENTITY_DISABLED_SETTINGS = {
    **settings.PEACHJAM,
    "CANONICAL_JUDGE_IDENTITY": False,
    "CANONICAL_JUDGE_IDENTITY_PUBLIC": False,
}
CANONICAL_JUDGE_IDENTITY_PUBLIC_SETTINGS = {
    **CANONICAL_JUDGE_IDENTITY_SETTINGS,
    "CANONICAL_JUDGE_IDENTITY_PUBLIC": True,
}
CANONICAL_JUDGE_IDENTITY_PUBLIC_FLYNOTE_SETTINGS = {
    **CANONICAL_JUDGE_IDENTITY_PUBLIC_SETTINGS,
    "SUMMARISE_USE_FLYNOTE_TREE": True,
    "SHOW_FLYNOTE_TOPICS": True,
}


class JudgeParsingTests(TestCase):
    def test_split_judge_display_name_keeps_only_surname_boldable(self):
        self.assertEqual(
            ("Kempe", ", Greg AJ"),
            split_judge_display_name("Kempe, Greg AJ"),
        )
        self.assertEqual(("Kempe", " AJ"), split_judge_display_name("Kempe AJ"))
        self.assertEqual(
            ("Da Silva", " Sallie"),
            split_judge_display_name("Da Silva Sallie"),
        )

    def test_parse_judge_name_splits_source_name_and_title(self):
        parts = judge_identity_service.parse_judge_name(" ABBAN, J.A. ")

        self.assertEqual("ABBAN, J.A.", parts["raw_name"])
        self.assertEqual("abban ja", parts["normalized_name"])
        self.assertEqual("abban", parts["base_name"])
        self.assertEqual("JA", parts["title"])

    def test_parse_judge_name_recognizes_jsc_as_title(self):
        parts = judge_identity_service.parse_judge_name("Acquah, JSC")

        self.assertEqual("acquah jsc", parts["normalized_name"])
        self.assertEqual("acquah", parts["base_name"])
        self.assertEqual("JSC", parts["title"])

    def test_parse_judge_name_recognizes_additional_trailing_titles(self):
        self.assertEqual(
            "VP",
            judge_identity_service.parse_judge_name("Thompson VP")["title"],
        )
        self.assertEqual(
            "PJ",
            judge_identity_service.parse_judge_name("Atoki PJ")["title"],
        )
        self.assertEqual(
            "DR",
            judge_identity_service.parse_judge_name("Kakai, DR")["title"],
        )
        self.assertEqual(
            "JCS",
            judge_identity_service.parse_judge_name("Sapong, JCS")["title"],
        )
        self.assertEqual(
            "CJ",
            judge_identity_service.parse_judge_name("Van Lare, AG, C J")["title"],
        )

    def test_canonical_name_from_aliases_strips_attached_title_suffix(self):
        self.assertEqual(
            "Acquaye",
            judge_identity_service.canonical_name_from_aliases(["Acquaye,JA"]),
        )

    def test_canonical_name_from_aliases_strips_jsc_suffix(self):
        self.assertEqual(
            "Adinyira",
            judge_identity_service.canonical_name_from_aliases(["Adinyira, JSC"]),
        )
        self.assertEqual(
            "Adjabeng",
            judge_identity_service.canonical_name_from_aliases(["Adjabeng JSC"]),
        )

    def test_canonical_name_from_aliases_strips_other_trailing_titles(self):
        self.assertEqual(
            "Thompson",
            judge_identity_service.canonical_name_from_aliases(["Thompson VP"]),
        )
        self.assertEqual(
            "Atoki",
            judge_identity_service.canonical_name_from_aliases(["Atoki PJ"]),
        )
        self.assertEqual(
            "Kakai",
            judge_identity_service.canonical_name_from_aliases(["Kakai, DR"]),
        )
        self.assertEqual(
            "Sapong",
            judge_identity_service.canonical_name_from_aliases(["Sapong, JCS"]),
        )
        self.assertEqual(
            "Edward Wiredu",
            judge_identity_service.canonical_name_from_aliases(
                ["Edward Wiredu, AG CJ"]
            ),
        )
        self.assertEqual(
            "Van Lare",
            judge_identity_service.canonical_name_from_aliases(["Van Lare, AG, C J"]),
        )
        self.assertEqual(
            "Mensah A.G",
            judge_identity_service.canonical_name_from_aliases(["Mensah A.G, JA"]),
        )

    def test_normalize_judge_name_folds_accents_without_dropping_letters(self):
        self.assertEqual("ore", judge_identity_service.normalize_judge_name("Orè"))
        self.assertEqual(
            "guisse", judge_identity_service.normalize_judge_name("Guissè")
        )


class JudgeAliasModelTests(TestCase):
    def test_save_sets_normalized_name_and_title(self):
        judge_person = JudgePerson.objects.create(full_name="Abban", slug="abban")

        alias = JudgeAlias.objects.create(
            judge_person=judge_person,
            name=" ABBAN, J.A. ",
        )

        self.assertEqual("abban ja", alias.normalized_name)
        self.assertEqual("JA", alias.title)


class BenchInlineFormTests(TestCase):
    fixtures = ["tests/countries", "tests/courts", "tests/languages"]

    def setUp(self):
        self.judgment = Judgment.objects.create(
            language=Language.objects.get(pk="en"),
            court=Court.objects.first(),
            date=datetime.date(2024, 1, 3),
            jurisdiction=Country.objects.get(pk="ZA"),
            case_name="Abban v Republic",
        )
        self.judge_person = JudgePerson.objects.create(
            full_name="Abban",
            slug="abban",
        )
        self.alias = JudgeAlias.objects.create(
            judge_person=self.judge_person,
            name="Abban, J.A.",
        )

    def test_form_uses_greg_labels_for_bench_fields(self):
        form = BenchInlineForm(instance=Bench(judgment=self.judgment))

        self.assertEqual("Extracted name", form.fields["extracted_name"].label)
        self.assertEqual("Judge title", form.fields["matched_alias"].label)
        self.assertEqual("Judge", form.fields["judge_person"].label)

    def test_extracted_name_is_readonly_when_prefilled(self):
        form = BenchInlineForm(
            initial={"extracted_name": "ABBAN, J.A."},
            instance=Bench(judgment=self.judgment),
        )

        self.assertTrue(form.fields["extracted_name"].widget.attrs["readonly"])

    def test_extracted_name_stays_editable_for_blank_manual_rows(self):
        form = BenchInlineForm(instance=Bench(judgment=self.judgment))

        self.assertNotIn("readonly", form.fields["extracted_name"].widget.attrs)

    def test_form_prefills_preview_options_for_unmatched_rows(self):
        form = BenchInlineForm(
            initial={
                "extracted_name": "Anukam J",
                "judge_person_suggestion": "Anukam",
            },
            instance=Bench(judgment=self.judgment),
        )

        self.assertEqual(
            BenchInlineForm.alias_preview_value,
            form.initial["matched_alias"],
        )
        self.assertEqual(
            BenchInlineForm.judge_preview_value,
            form.initial["judge_person"],
        )
        self.assertIn(
            'option value="__alias_preview__" selected>Anukam J</option>',
            str(form["matched_alias"]),
        )
        self.assertIn(
            'option value="__judge_preview__" selected>Anukam</option>',
            str(form["judge_person"]),
        )

    def test_form_uses_alias_to_fill_hidden_legacy_judge(self):
        form = BenchInlineForm(
            data={
                "judgment": self.judgment.pk,
                "extracted_name": "ABBAN, J.A.",
                "matched_alias": self.alias.pk,
            },
            instance=Bench(judgment=self.judgment),
        )

        self.assertTrue(form.is_valid(), form.errors)
        bench = form.save()

        self.assertEqual("Abban, J.A.", bench.judge.name)
        self.assertEqual(self.judge_person, bench.judge_person)

    def test_form_uses_extracted_name_when_no_alias_exists(self):
        form = BenchInlineForm(
            data={
                "judgment": self.judgment.pk,
                "extracted_name": "New Judge, JA",
                "matched_alias": BenchInlineForm.alias_preview_value,
                "judge_person": BenchInlineForm.judge_preview_value,
            },
            initial={
                "judge_person_suggestion": "New Judge",
            },
            instance=Bench(judgment=self.judgment),
        )

        self.assertTrue(form.is_valid(), form.errors)
        bench = form.save()

        self.assertEqual("New Judge, JA", bench.judge.name)
        self.assertEqual("New Judge", bench.judge_person.full_name)
        self.assertEqual("New Judge, JA", bench.matched_alias.name)
        self.assertTrue(Judge.objects.filter(name="New Judge, JA").exists())

    def test_form_creates_alias_from_source_name_for_selected_canonical_judge(self):
        form = BenchInlineForm(
            data={
                "judgment": self.judgment.pk,
                "extracted_name": "Abban JA",
                "judge_person": self.judge_person.pk,
            },
            instance=Bench(judgment=self.judgment),
        )

        self.assertTrue(form.is_valid(), form.errors)
        bench = form.save()

        self.assertIsNotNone(bench.matched_alias_id)
        self.assertEqual("Abban JA", bench.matched_alias.name)
        self.assertEqual(self.judge_person, bench.matched_alias.judge_person)
        self.assertEqual(self.judge_person, bench.judge_person)

    def test_form_reuses_existing_canonical_judge_when_alias_is_missing(self):
        form = BenchInlineForm(
            data={
                "judgment": self.judgment.pk,
                "extracted_name": "Abban JA",
            },
            instance=Bench(judgment=self.judgment),
        )

        self.assertTrue(form.is_valid(), form.errors)
        bench = form.save()

        self.assertEqual(self.judge_person.pk, bench.judge_person_id)
        self.assertEqual("Abban JA", bench.matched_alias.name)
        self.assertEqual(self.judge_person.pk, bench.matched_alias.judge_person_id)

    def test_form_uses_selected_canonical_judge_when_editor_overrides_suggestion(self):
        other_person = JudgePerson.objects.create(
            full_name="Anukum",
            slug="anukum",
        )
        form = BenchInlineForm(
            data={
                "judgment": self.judgment.pk,
                "extracted_name": "Anukam J",
                "judge_person": other_person.pk,
            },
            instance=Bench(judgment=self.judgment),
        )

        self.assertTrue(form.is_valid(), form.errors)
        bench = form.save()

        self.assertEqual("Anukam J", bench.matched_alias.name)
        self.assertEqual(other_person.pk, bench.judge_person_id)


class JudgeIdentityResolutionTests(TestCase):
    def test_resolve_judge_person_reuses_existing_alias_owner(self):
        judge_person = JudgePerson.objects.create(full_name="Abban", slug="abban")
        alias = JudgeAlias.objects.create(
            judge_person=judge_person,
            name="ABBAN, J.A.",
        )

        resolved = judge_identity_service.resolve_judge_person(["Abban JA"])

        self.assertEqual(judge_person.pk, resolved["judge_person"].pk)
        self.assertEqual([alias.pk], [row.pk for row in resolved["aliases"]])
        self.assertEqual("Abban", resolved["canonical_name"])
        self.assertFalse(resolved["created"])

    def test_resolve_judge_person_reuses_existing_person_without_alias(self):
        judge_person = JudgePerson.objects.create(full_name="ABBAN", slug="abban")

        resolved = judge_identity_service.resolve_judge_person(["Abban JA"])

        self.assertEqual(judge_person.pk, resolved["judge_person"].pk)
        self.assertEqual([], resolved["aliases"])
        self.assertEqual("Abban", resolved["canonical_name"])
        self.assertFalse(resolved["created"])

    def test_resolve_judge_person_creates_new_person_when_needed(self):
        resolved = judge_identity_service.resolve_judge_person(["Abban JA"])

        self.assertTrue(resolved["created"])
        self.assertIsNotNone(resolved["judge_person"].pk)
        self.assertEqual("Abban", resolved["judge_person"].full_name)
        self.assertEqual([], resolved["aliases"])

    def test_resolve_judge_person_dry_run_returns_unsaved_person(self):
        resolved = judge_identity_service.resolve_judge_person(
            ["Abban JA"],
            dry_run=True,
        )

        self.assertTrue(resolved["created"])
        self.assertIsNone(resolved["judge_person"].pk)
        self.assertEqual("Abban", resolved["judge_person"].full_name)
        self.assertEqual([], resolved["aliases"])


class JudgmentFormExtractorUrlTests(TestCase):
    @override_settings(DEBUG=False)
    def test_extractor_url_is_hidden_when_extractor_is_disabled(self):
        form = JudgmentForm(instance=Judgment())

        with patch("peachjam.admin.ExtractorService.enabled", return_value=False):
            self.assertIsNone(form.extractor_url)

    def test_extractor_url_is_available_when_extractor_is_enabled(self):
        form = JudgmentForm(instance=Judgment())

        with patch("peachjam.admin.ExtractorService.enabled", return_value=True):
            self.assertEqual(
                reverse("admin:peachjam_extract_judgment"),
                form.extractor_url,
            )


@override_settings(PEACHJAM=CANONICAL_JUDGE_IDENTITY_SETTINGS)
class ExtractorJudgeIdentityTests(TestCase):
    fixtures = ["tests/countries", "tests/courts", "tests/languages"]

    def setUp(self):
        self.extractor = ExtractorService()
        self.judge_person = JudgePerson.objects.create(full_name="Abban", slug="abban")
        self.alias = JudgeAlias.objects.create(
            judge_person=self.judge_person,
            name="Abban JA",
        )
        self.legacy_exact = Judge.objects.create(name="ABBAN, J.A.")
        self.legacy_alias = Judge.objects.create(name="Abban JA")

    def test_process_judgment_details_builds_bench_rows_with_suggestions(self):
        details = {
            "court": Court.objects.first().name,
            "date": "2024-01-03",
            "judges": ["ABBAN, J.A.", "Abban JA", "Unknown J"],
            "language": "eng",
        }

        self.extractor.process_judgment_details(details)

        self.assertEqual(
            ["ABBAN, J.A.", "Abban JA", "Unknown J"],
            details["extracted_judges"],
        )
        self.assertEqual(2, len(details["judges"]))
        self.assertEqual(3, len(details["bench_rows"]))

        first_row, second_row, third_row = details["bench_rows"]

        self.assertEqual(self.legacy_exact.pk, first_row["judge"].pk)
        self.assertEqual("ABBAN, J.A.", first_row["extracted_name"])
        self.assertEqual(self.alias.pk, first_row["matched_alias"].pk)
        self.assertEqual(self.judge_person.pk, first_row["judge_person"].pk)

        self.assertEqual(self.legacy_alias.pk, second_row["judge"].pk)
        self.assertEqual("Abban JA", second_row["extracted_name"])
        self.assertEqual(self.alias.pk, second_row["matched_alias"].pk)
        self.assertEqual(self.judge_person.pk, second_row["judge_person"].pk)

        self.assertIsNone(third_row["judge"])
        self.assertEqual("Unknown J", third_row["extracted_name"])
        self.assertIsNone(third_row["matched_alias"])
        self.assertIsNone(third_row["judge_person"])

    def test_process_judgment_details_leaves_ambiguous_aliases_unmatched_but_prefills_judge(
        self,
    ):
        other_person = JudgePerson.objects.create(
            full_name="Another Abban",
            slug="another-abban",
        )
        JudgeAlias.objects.create(
            judge_person=other_person,
            name="ABBAN, J.A.",
        )
        details = {
            "judges": ["ABBAN, J.A."],
        }

        self.extractor.process_judgment_details(details)

        bench_row = details["bench_rows"][0]
        self.assertIsNone(bench_row["matched_alias"])
        self.assertEqual(self.judge_person.pk, bench_row["judge_person"].pk)

    def test_process_judgment_details_prefills_existing_canonical_judge_without_alias(
        self,
    ):
        existing_person = JudgePerson.objects.create(
            full_name="Unknown",
            slug="unknown",
        )
        details = {
            "judges": ["Unknown J"],
        }

        self.extractor.process_judgment_details(details)

        bench_row = details["bench_rows"][0]
        self.assertIsNone(bench_row["matched_alias"])
        self.assertEqual(existing_person.pk, bench_row["judge_person"].pk)


@override_settings(PEACHJAM=CANONICAL_JUDGE_IDENTITY_DISABLED_SETTINGS)
class ExtractorLegacyJudgeTests(TestCase):
    fixtures = ["tests/countries", "tests/courts", "tests/languages"]

    def test_process_judgment_details_uses_legacy_judges_by_default(self):
        legacy_judge = Judge.objects.create(name="ABBAN, J.A.")
        details = {
            "court": Court.objects.first().name,
            "date": "2024-01-03",
            "judges": ["ABBAN, J.A.", "Unknown J"],
            "language": "eng",
        }

        ExtractorService().process_judgment_details(details)

        self.assertEqual([legacy_judge], details["judges"])
        self.assertNotIn("bench_rows", details)
        self.assertNotIn("extracted_judges", details)


@override_settings(PEACHJAM=CANONICAL_JUDGE_IDENTITY_DISABLED_SETTINGS)
class CanonicalJudgeIdentityRolloutGateTests(TestCase):
    fixtures = ["tests/countries", "tests/courts", "tests/languages"]

    @override_settings(PEACHJAM={})
    def test_missing_setting_uses_legacy_bench_inline(self):
        judgment_admin = JudgmentAdmin(Judgment, admin.site)

        self.assertFalse(JudgePerson.canonical_identity_enabled())
        self.assertIs(LegacyBenchInline, judgment_admin.get_inlines(None)[0])

    def test_judgment_admin_uses_legacy_bench_inline_by_default(self):
        judgment_admin = JudgmentAdmin(Judgment, admin.site)

        self.assertIs(LegacyBenchInline, judgment_admin.get_inlines(None)[0])

    @override_settings(PEACHJAM=CANONICAL_JUDGE_IDENTITY_SETTINGS)
    def test_judgment_admin_uses_canonical_bench_inline_when_enabled(self):
        judgment_admin = JudgmentAdmin(Judgment, admin.site)

        self.assertIs(BenchInline, judgment_admin.get_inlines(None)[0])

    def test_judge_identity_workflow_is_disabled_by_default(self):
        admin_user = User.objects.create_user(
            username="judge-admin-disabled@example.com",
            email="judge-admin-disabled@example.com",
            password="password",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(admin_user)

        response = self.client.get(reverse("peachjam_judgeperson_workflow"))

        self.assertEqual(403, response.status_code)


@override_settings(PEACHJAM=CANONICAL_JUDGE_IDENTITY_DISABLED_SETTINGS)
class CanonicalJudgeIdentityPublicPageTests(TestCase):
    fixtures = ["tests/countries", "tests/courts", "tests/languages"]

    def setUp(self):
        self.legacy_judge = Judge.objects.create(name="ABBAN, J.A.")
        self.judge_person = JudgePerson.objects.create(
            full_name="Justice Abban",
            slug="justice-abban",
        )
        self.alias = JudgeAlias.objects.create(
            judge_person=self.judge_person,
            name="ABBAN, J.A.",
        )
        self.judgment = Judgment.objects.create(
            language=Language.objects.get(pk="en"),
            court=Court.objects.first(),
            date=datetime.date(2024, 1, 3),
            jurisdiction=Country.objects.get(pk="ZA"),
            case_name="Abban v Republic",
        )
        Bench.objects.create(
            judgment=self.judgment,
            judge=self.legacy_judge,
            judge_person=self.judge_person,
            matched_alias=self.alias,
        )

    def judge_name_markup(self, name):
        surname, remainder = split_judge_display_name(name)
        return f'<strong class="judge-name__surname">{surname}</strong>{remainder}'

    def test_public_setting_is_disabled_by_default(self):
        self.assertFalse(JudgePerson.canonical_identity_public_enabled())

    def test_judgment_detail_uses_legacy_judge_by_default(self):
        response = self.client.get(self.judgment.get_absolute_url())

        self.assertEqual(200, response.status_code)
        self.assertEqual([self.legacy_judge], response.context["judges"])
        self.assertContains(response, "ABBAN, J.A.")
        self.assertContains(response, "?judges=ABBAN%2C%20J.A.")

    @override_settings(PEACHJAM=CANONICAL_JUDGE_IDENTITY_PUBLIC_SETTINGS)
    def test_judgment_detail_uses_canonical_judge_when_public_enabled(self):
        response = self.client.get(self.judgment.get_absolute_url())

        self.assertEqual(200, response.status_code)
        self.assertEqual([self.judge_person], response.context["judges"])
        self.assertContains(response, "Justice Abban")
        self.assertContains(response, self.judge_person.get_absolute_url())

    def test_judge_detail_is_disabled_by_default(self):
        response = self.client.get(self.judge_person.get_absolute_url())

        self.assertEqual(404, response.status_code)

    def test_judge_list_is_disabled_by_default(self):
        response = self.client.get(reverse("judges"))

        self.assertEqual(404, response.status_code)

    @override_settings(PEACHJAM=CANONICAL_JUDGE_IDENTITY_PUBLIC_SETTINGS)
    def test_judge_list_shows_linked_canonical_judges(self):
        other_judge = Judge.objects.create(name="Other J")
        other_person = JudgePerson.objects.create(
            full_name="Other Judge",
            slug="other-judge",
        )
        unlinked_person = JudgePerson.objects.create(
            full_name="Unlinked Judge",
            slug="unlinked-judge",
        )
        other_judgment = Judgment.objects.create(
            language=Language.objects.get(pk="en"),
            court=Court.objects.first(),
            date=datetime.date(2024, 1, 4),
            jurisdiction=Country.objects.get(pk="ZA"),
            case_name="Other v Republic",
        )
        Bench.objects.create(
            judgment=other_judgment,
            judge=other_judge,
            judge_person=other_person,
        )

        response = self.client.get(reverse("judges"))

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "Judges")
        self.assertContains(
            response,
            self.judge_name_markup(self.judge_person.full_name),
            html=True,
        )
        self.assertContains(response, self.judge_person.get_absolute_url())
        self.assertContains(
            response,
            self.judge_name_markup(other_person.full_name),
            html=True,
        )
        self.assertNotContains(
            response,
            self.judge_name_markup(unlinked_person.full_name),
            html=True,
        )
        self.assertEqual(2, response.context["judge_count"])

    @override_settings(PEACHJAM=CANONICAL_JUDGE_IDENTITY_PUBLIC_SETTINGS)
    def test_judge_list_paginates_ten_judges_per_page(self):
        for index in range(10):
            legacy_judge = Judge.objects.create(name=f"Pagination Judge {index:02d}")
            judge_person = JudgePerson.objects.create(
                full_name=f"Pagination Judge {index:02d}"
            )
            judgment = Judgment.objects.create(
                language=Language.objects.get(pk="en"),
                court=Court.objects.first(),
                date=datetime.date(2024, 1, 4),
                jurisdiction=Country.objects.get(pk="ZA"),
                case_name=f"Pagination matter {index:02d}",
            )
            Bench.objects.create(
                judgment=judgment,
                judge=legacy_judge,
                judge_person=judge_person,
            )

        response = self.client.get(reverse("judges"))

        self.assertEqual(200, response.status_code)
        self.assertTrue(response.context["is_paginated"])
        self.assertEqual(11, response.context["judge_count"])
        self.assertEqual(10, len(response.context["judges"]))
        self.assertEqual(2, response.context["paginator"].num_pages)

        second_page = self.client.get(reverse("judges"), {"page": 2})

        self.assertEqual(200, second_page.status_code)
        self.assertEqual(1, len(second_page.context["judges"]))

    @override_settings(PEACHJAM=CANONICAL_JUDGE_IDENTITY_PUBLIC_SETTINGS)
    def test_judge_list_filters_by_search(self):
        other_judge = Judge.objects.create(name="Other J")
        other_person = JudgePerson.objects.create(
            full_name="Other Judge",
            slug="other-judge",
        )
        other_judgment = Judgment.objects.create(
            language=Language.objects.get(pk="en"),
            court=Court.objects.first(),
            date=datetime.date(2024, 1, 4),
            jurisdiction=Country.objects.get(pk="ZA"),
            case_name="Other v Republic",
        )
        Bench.objects.create(
            judgment=other_judgment,
            judge=other_judge,
            judge_person=other_person,
        )

        response = self.client.get(reverse("judges"), {"q": "abban"})

        self.assertEqual(200, response.status_code)
        self.assertContains(
            response,
            self.judge_name_markup(self.judge_person.full_name),
            html=True,
        )
        self.assertNotContains(
            response,
            self.judge_name_markup(other_person.full_name),
            html=True,
        )
        self.assertEqual(1, response.context["judge_count"])

    @override_settings(PEACHJAM=CANONICAL_JUDGE_IDENTITY_PUBLIC_SETTINGS)
    def test_judge_list_sorts_names_z_to_a(self):
        other_person = JudgePerson.objects.create(full_name="Zulu Judge")
        other_judgment = Judgment.objects.create(
            language=Language.objects.get(pk="en"),
            court=Court.objects.first(),
            date=datetime.date(2024, 1, 4),
            jurisdiction=Country.objects.get(pk="ZA"),
            case_name="Other v Republic",
        )
        Bench.objects.create(
            judgment=other_judgment,
            judge=Judge.objects.create(name="Zulu J"),
            judge_person=other_person,
        )

        response = self.client.get(reverse("judges"), {"sort": "name_desc"})

        self.assertEqual(200, response.status_code)
        self.assertEqual([other_person, self.judge_person], response.context["judges"])
        self.assertEqual(
            ["Z", "J"], [letter for letter, _ in response.context["grouped_judges"]]
        )

    @override_settings(PEACHJAM=CANONICAL_JUDGE_IDENTITY_PUBLIC_SETTINGS)
    def test_judge_list_filters_by_active_year(self):
        other_judge = Judge.objects.create(name="Other J")
        other_person = JudgePerson.objects.create(
            full_name="Other Judge",
            slug="other-judge",
        )
        other_judgment = Judgment.objects.create(
            language=Language.objects.get(pk="en"),
            court=Court.objects.first(),
            date=datetime.date(2019, 1, 4),
            jurisdiction=Country.objects.get(pk="ZA"),
            case_name="Other v Republic",
        )
        Bench.objects.create(
            judgment=other_judgment,
            judge=other_judge,
            judge_person=other_person,
        )

        response = self.client.get(
            reverse("judges"), {"year_from": "2020", "year_to": "2024"}
        )

        self.assertEqual(200, response.status_code)
        self.assertContains(
            response,
            self.judge_name_markup(self.judge_person.full_name),
            html=True,
        )
        self.assertNotContains(
            response,
            self.judge_name_markup(other_person.full_name),
            html=True,
        )
        self.assertEqual(1, response.context["judge_count"])
        self.assertContains(response, 'aria-current="page">2020–2024</a>')

    @override_settings(PEACHJAM=CANONICAL_JUDGE_IDENTITY_PUBLIC_SETTINGS)
    def test_judge_list_combines_multiple_courts_and_year_ranges(self):
        other_court = Court.objects.create(
            name="Appeal Court",
            code="AC",
            court_class=self.judgment.court.court_class,
        )
        other_person = JudgePerson.objects.create(full_name="Other Judge")
        other_judgment = Judgment.objects.create(
            language=Language.objects.get(pk="en"),
            court=other_court,
            date=datetime.date(2019, 1, 4),
            jurisdiction=Country.objects.get(pk="ZA"),
            case_name="Other v Republic",
        )
        Bench.objects.create(
            judgment=other_judgment,
            judge=Judge.objects.create(name="Other J"),
            judge_person=other_person,
        )

        response = self.client.get(
            reverse("judges"),
            {
                "courts": [self.judgment.court.name, other_court.name],
                "years": ["2024", "2019"],
            },
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual(2, response.context["judge_count"])
        self.assertContains(
            response,
            self.judge_name_markup(self.judge_person.full_name),
            html=True,
        )
        self.assertContains(
            response,
            self.judge_name_markup(other_person.full_name),
            html=True,
        )
        selected_court = next(
            item
            for item in response.context["judge_court_filters"]
            if item["label"] == self.judgment.court.name
        )
        toggled_courts = parse_qs(urlparse(selected_court["url"]).query)["courts"]
        self.assertEqual([other_court.name], toggled_courts)
        selected_year_range = next(
            item
            for item in response.context["judge_year_filters"]
            if item["label"] == "2020–2024"
        )
        toggled_years = parse_qs(urlparse(selected_year_range["url"]).query)["years"]
        self.assertEqual(["2019"], toggled_years)

    @override_settings(PEACHJAM=CANONICAL_JUDGE_IDENTITY_PUBLIC_FLYNOTE_SETTINGS)
    def test_judge_list_filters_by_flynote_topic_and_descendants(self):
        civil = Flynote.add_root(name="Civil law")
        contract = civil.add_child(name="Contract")
        JudgmentFlynote.objects.create(document=self.judgment, flynote=contract)

        other_person = JudgePerson.objects.create(
            full_name="Other Judge",
            slug="other-judge",
        )
        other_judgment = Judgment.objects.create(
            language=Language.objects.get(pk="en"),
            court=Court.objects.first(),
            date=datetime.date(2024, 1, 4),
            jurisdiction=Country.objects.get(pk="ZA"),
            case_name="Other v Republic",
        )
        Bench.objects.create(
            judgment=other_judgment,
            judge=Judge.objects.create(name="Other J"),
            judge_person=other_person,
        )
        criminal = Flynote.add_root(name="Criminal law")
        offence = criminal.add_child(name="Offences")
        JudgmentFlynote.objects.create(document=other_judgment, flynote=offence)

        response = self.client.get(reverse("judges"), {"topic": civil.pk})

        self.assertEqual(200, response.status_code)
        self.assertContains(
            response,
            self.judge_name_markup(self.judge_person.full_name),
            html=True,
        )
        self.assertNotContains(
            response,
            self.judge_name_markup(other_person.full_name),
            html=True,
        )
        self.assertContains(response, "Topics")
        self.assertNotContains(response, ">ALL</a>")
        self.assertContains(response, "Civil law")
        self.assertEqual([civil], response.context["selected_flynote_topics"])
        self.assertEqual(1, response.context["judge_count"])
        self.assertContains(response, f'name="topics" value="{civil.pk}"')

        response = self.client.get(
            reverse("judges"), {"topics": [civil.pk, criminal.pk]}
        )

        self.assertEqual(2, response.context["judge_count"])
        self.assertEqual(
            {civil, criminal}, set(response.context["selected_flynote_topics"])
        )
        civil_filter = next(
            item
            for item in response.context["judge_topic_filters"]
            if item["label"] == civil.name
        )
        self.assertEqual(
            [str(criminal.pk)], parse_qs(urlparse(civil_filter["url"]).query)["topics"]
        )

    @override_settings(PEACHJAM=CANONICAL_JUDGE_IDENTITY_PUBLIC_SETTINGS)
    def test_judgment_list_filters_by_canonical_judge_when_public_enabled(self):
        other_judge = Judge.objects.create(name="Other J")
        other_person = JudgePerson.objects.create(
            full_name="Other Judge",
            slug="other-judge",
        )
        other_judgment = Judgment.objects.create(
            language=Language.objects.get(pk="en"),
            court=Court.objects.first(),
            date=datetime.date(2024, 1, 4),
            jurisdiction=Country.objects.get(pk="ZA"),
            case_name="Other v Republic",
        )
        Bench.objects.create(
            judgment=other_judgment,
            judge=other_judge,
            judge_person=other_person,
        )

        response = self.client.get(
            reverse("court", kwargs={"code": "all"}),
            {"judge_people": [str(self.judge_person.pk)]},
        )

        self.assertEqual(200, response.status_code)
        self.assertIn(self.judgment, response.context["documents"])
        self.assertNotIn(other_judgment, response.context["documents"])
        self.assertIn("judge_people", response.context["facet_data"])
        self.assertNotIn("judges", response.context["facet_data"])
        self.assertIn(
            (
                str(self.judge_person.pk),
                self.judge_person.full_name,
                self.judge_person.get_absolute_url(),
            ),
            response.context["facet_data"]["judge_people"]["options"],
        )
        self.assertContains(response, f'href="{self.judge_person.get_absolute_url()}"')

    @override_settings(PEACHJAM=CANONICAL_JUDGE_IDENTITY_PUBLIC_SETTINGS)
    def test_judge_detail_lists_canonical_judge_judgments(self):
        other_judge = Judge.objects.create(name="Other J")
        other_person = JudgePerson.objects.create(
            full_name="Other Judge",
            slug="other-judge",
        )
        other_judgment = Judgment.objects.create(
            language=Language.objects.get(pk="en"),
            court=Court.objects.first(),
            date=datetime.date(2024, 1, 4),
            jurisdiction=Country.objects.get(pk="ZA"),
            case_name="Other v Republic",
        )
        Bench.objects.create(
            judgment=other_judgment,
            judge=other_judge,
            judge_person=other_person,
        )

        response = self.client.get(self.judge_person.get_absolute_url())

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "Justice Abban")
        self.assertIn(self.judgment, response.context["documents"])
        self.assertNotIn(other_judgment, response.context["documents"])
        self.assertContains(response, "Courts")
        self.assertNotContains(response, ">ALL</a>")
        self.assertNotContains(response, "Alphabet")

    @override_settings(PEACHJAM=CANONICAL_JUDGE_IDENTITY_PUBLIC_SETTINGS)
    def test_judge_detail_htmx_response_skips_dashboard_analysis(self):
        with patch.object(
            JudgePersonDetailView, "get_citation_analysis"
        ) as get_citation_analysis:
            response = self.client.get(
                self.judge_person.get_absolute_url(),
                HTTP_HX_REQUEST="true",
                HTTP_HX_TARGET="judge-detail-filters",
            )

        self.assertEqual(200, response.status_code)
        self.assertTemplateUsed(
            response, "peachjam/_judge_detail_document_table_form.html"
        )
        get_citation_analysis.assert_not_called()
        self.assertNotContains(response, "Judicial activity")

    @override_settings(PEACHJAM=CANONICAL_JUDGE_IDENTITY_PUBLIC_SETTINGS)
    def test_judge_surname_is_bold_in_list_and_detail_views(self):
        self.judge_person.full_name = "Kempe, Greg AJ"
        self.judge_person.save(update_fields=["full_name"])
        expected_name = '<strong class="judge-name__surname">Kempe</strong>, Greg AJ'

        list_response = self.client.get(reverse("judges"))
        detail_response = self.client.get(self.judge_person.get_absolute_url())

        self.assertContains(list_response, expected_name, html=True)
        self.assertContains(detail_response, expected_name, html=True)

    @override_settings(PEACHJAM=CANONICAL_JUDGE_IDENTITY_PUBLIC_SETTINGS)
    def test_judge_detail_filters_judgments_by_court_and_year(self):
        other_court = Court.objects.create(
            name="Appeal Court",
            code="AC",
            court_class=self.judgment.court.court_class,
        )
        other_judgment = Judgment.objects.create(
            language=Language.objects.get(pk="en"),
            court=other_court,
            date=datetime.date(2025, 2, 4),
            jurisdiction=Country.objects.get(pk="ZA"),
            case_name="Second v Republic",
        )
        Bench.objects.create(
            judgment=other_judgment,
            judge=self.legacy_judge,
            judge_person=self.judge_person,
            matched_alias=self.alias,
        )

        response = self.client.get(
            self.judge_person.get_absolute_url(),
            {"courts": self.judgment.court.name},
        )

        self.assertEqual(200, response.status_code)
        self.assertIn(self.judgment, response.context["documents"])
        self.assertNotIn(other_judgment, response.context["documents"])
        self.assertEqual(
            [self.judgment.court.name], response.context["selected_judge_courts"]
        )
        self.assertContains(
            response,
            f'name="courts" value="{self.judgment.court.name}"',
        )
        self.assertContains(response, 'hx-disinherit="hx-include"')

        response = self.client.get(
            self.judge_person.get_absolute_url(), {"years": "2025"}
        )

        self.assertEqual(200, response.status_code)
        self.assertNotIn(self.judgment, response.context["documents"])
        self.assertIn(other_judgment, response.context["documents"])
        self.assertEqual(["2025"], response.context["selected_judge_years"])

    @override_settings(PEACHJAM=CANONICAL_JUDGE_IDENTITY_PUBLIC_FLYNOTE_SETTINGS)
    def test_judge_detail_filters_judgments_by_flynote_topic_and_descendants(self):
        civil = Flynote.add_root(name="Civil law")
        contract = civil.add_child(name="Contract")
        JudgmentFlynote.objects.create(document=self.judgment, flynote=contract)

        other_judgment = Judgment.objects.create(
            language=Language.objects.get(pk="en"),
            court=Court.objects.first(),
            date=datetime.date(2025, 2, 4),
            jurisdiction=Country.objects.get(pk="ZA"),
            case_name="Second v Republic",
        )
        Bench.objects.create(
            judgment=other_judgment,
            judge=self.legacy_judge,
            judge_person=self.judge_person,
            matched_alias=self.alias,
        )
        criminal = Flynote.add_root(name="Criminal law")
        offence = criminal.add_child(name="Offences")
        JudgmentFlynote.objects.create(document=other_judgment, flynote=offence)

        response = self.client.get(
            self.judge_person.get_absolute_url(), {"topic": civil.pk}
        )

        self.assertEqual(200, response.status_code)
        self.assertIn(self.judgment, response.context["documents"])
        self.assertNotIn(other_judgment, response.context["documents"])
        self.assertEqual([civil], response.context["selected_flynote_topics"])
        self.assertNotContains(response, ">ALL</a>")
        self.assertContains(response, "Civil law")
        self.assertContains(response, "Criminal law")
        self.assertContains(response, f'name="topics" value="{civil.pk}"')

        response = self.client.get(
            self.judge_person.get_absolute_url(),
            {"topics": [civil.pk, criminal.pk]},
        )

        self.assertIn(self.judgment, response.context["documents"])
        self.assertIn(other_judgment, response.context["documents"])
        self.assertEqual(
            {civil, criminal}, set(response.context["selected_flynote_topics"])
        )
        civil_filter = next(
            item
            for item in response.context["judge_topic_filters"]
            if item["label"] == civil.name
        )
        self.assertEqual(
            [str(criminal.pk)], parse_qs(urlparse(civil_filter["url"]).query)["topics"]
        )

    @override_settings(PEACHJAM=CANONICAL_JUDGE_IDENTITY_PUBLIC_SETTINGS)
    def test_judge_detail_shows_summary_context(self):
        second_judgment = Judgment.objects.create(
            language=Language.objects.get(pk="en"),
            court=Court.objects.first(),
            date=datetime.date(2025, 2, 4),
            jurisdiction=Country.objects.get(pk="ZA"),
            case_name="Second v Republic",
        )
        Bench.objects.create(
            judgment=second_judgment,
            judge=self.legacy_judge,
            judge_person=self.judge_person,
            matched_alias=self.alias,
        )

        response = self.client.get(self.judge_person.get_absolute_url())

        self.assertEqual(200, response.status_code)
        self.assertEqual(2024, response.context["judge_first_year"])
        self.assertEqual(2025, response.context["judge_latest_year"])
        self.assertEqual(2, response.context["judge_judgment_count"])
        self.assertEqual(["ABBAN, J.A."], response.context["judge_aliases"])
        self.assertEqual(
            [
                {
                    "judgment__court__name": self.judgment.court.name,
                    "judgment_count": 2,
                    "first_year": 2024,
                    "latest_year": 2025,
                    "percentage": 100,
                }
            ],
            response.context["judge_court_chart"],
        )
        self.assertEqual(
            [
                {"year": 2024, "judgment_count": 1, "percentage": 100},
                {"year": 2025, "judgment_count": 1, "percentage": 100},
            ],
            response.context["judge_year_activity"],
        )
        self.assertEqual(["JA"], response.context["judge_titles"])
        self.assertEqual(1.0, response.context["judge_average_per_active_year"])
        self.assertEqual(2, len(response.context["judge_year_activity"]))
        self.assertContains(response, "Judicial record profile")
        self.assertContains(response, "Judgments by year")

    @override_settings(PEACHJAM=CANONICAL_JUDGE_IDENTITY_PUBLIC_SETTINGS)
    def test_judge_detail_shows_citation_network_context(self):
        other_person = JudgePerson.objects.create(
            full_name="Justice Other",
            slug="justice-other",
        )
        other_judgment = Judgment.objects.create(
            language=Language.objects.get(pk="en"),
            court=Court.objects.first(),
            date=datetime.date(2025, 4, 2),
            jurisdiction=Country.objects.get(pk="ZA"),
            case_name="Other v Republic",
        )
        Bench.objects.create(
            judgment=other_judgment,
            judge=Judge.objects.create(name="Other J"),
            judge_person=other_person,
        )
        ExtractedCitation.objects.create(
            citing_work=other_judgment.work,
            target_work=self.judgment.work,
        )
        ExtractedCitation.objects.create(
            citing_work=self.judgment.work,
            target_work=other_judgment.work,
        )

        response = self.client.get(self.judge_person.get_absolute_url())

        self.assertEqual(200, response.status_code)
        analysis = response.context["judge_citation_analysis"]
        self.assertEqual(1, analysis["incoming_count"])
        self.assertEqual(1, analysis["outgoing_count"])
        self.assertEqual(
            "Justice Other", analysis["citing_judges"][0]["judge_person__full_name"]
        )
        self.assertEqual(
            "Justice Other", analysis["cited_judges"][0]["judge_person__full_name"]
        )
        self.assertEqual(self.judgment, analysis["most_cited_judgments"][0])
        self.assertEqual(
            1,
            analysis["most_cited_judgments"][0].incoming_citation_count,
        )
        self.assertContains(response, "Citation influence")
        self.assertContains(response, "Justice Other")


@override_settings(PEACHJAM=CANONICAL_JUDGE_IDENTITY_DISABLED_SETTINGS)
class JudgmentExtractLegacyViewRenderingTests(TestCase):
    fixtures = ["tests/countries", "tests/courts", "tests/languages"]

    def setUp(self):
        self.user = User.objects.create_superuser(
            username="legacy-admin",
            email="legacy-admin@example.com",
            password="password",
        )
        self.client.force_login(self.user)

    def test_extract_view_uses_legacy_bench_inline_by_default(self):
        Judge.objects.create(name="Anukam J")
        file = SimpleUploadedFile(
            "judgment.pdf",
            b"%PDF-1.4 fake",
            content_type="application/pdf",
        )

        with patch(
            "peachjam.admin.ExtractorService.extract_judgment_details",
            return_value={
                "language": "eng",
                "court": Court.objects.first().name,
                "date": "2025-02-03",
                "judges": ["Anukam J"],
                "must_be_anonymised": True,
                "case_numbers": [],
            },
        ):
            response = self.client.post(
                reverse("admin:peachjam_extract_judgment"),
                {"file": file},
            )

        self.assertEqual(200, response.status_code)
        content = response.content.decode()
        self.assertIn("Anukam J", content)
        self.assertNotIn('value="__alias_preview__"', content)
        self.assertNotIn('value="__judge_preview__"', content)


@override_settings(PEACHJAM=CANONICAL_JUDGE_IDENTITY_SETTINGS)
class JudgmentExtractViewRenderingTests(TestCase):
    fixtures = ["tests/countries", "tests/courts", "tests/languages"]

    def setUp(self):
        self.user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="password",
        )
        self.client.force_login(self.user)

    @override_settings(
        DEBUG=True,
        INSTALLED_APPS=[
            app for app in settings.INSTALLED_APPS if app != "debug_toolbar"
        ],
        MIDDLEWARE=[
            middleware
            for middleware in settings.MIDDLEWARE
            if middleware != "debug_toolbar.middleware.DebugToolbarMiddleware"
        ],
    )
    def test_extract_view_renders_preview_options_for_unmatched_judges(self):
        file = SimpleUploadedFile(
            "judgment.pdf",
            b"%PDF-1.4 fake",
            content_type="application/pdf",
        )

        with patch(
            "peachjam.admin.ExtractorService.extract_judgment_details",
            side_effect=ExtractorError("boom"),
        ):
            response = self.client.post(
                reverse("admin:peachjam_extract_judgment"),
                {"file": file},
            )

        self.assertEqual(200, response.status_code)
        content = response.content.decode()
        self.assertIn("Anukam J", content)
        self.assertIn('value="__alias_preview__"', content)
        self.assertIn(">Anukam<", content)
        self.assertIn('value="__judge_preview__"', content)


class BackfillJudgePeopleCommandTests(TestCase):
    fixtures = ["tests/countries", "tests/courts", "tests/languages"]

    def setUp(self):
        self.legacy_judge_one = Judge.objects.create(name="Abban JA")
        self.legacy_judge_two = Judge.objects.create(name="ABBAN, J.A.")
        self.legacy_judge_three = Judge.objects.create(name="Abban, J")
        self.judgment = Judgment.objects.create(
            language=Language.objects.get(pk="en"),
            court=Court.objects.first(),
            date=datetime.date(2024, 1, 3),
            jurisdiction=Country.objects.get(pk="ZA"),
            case_name="Abban v Republic",
        )
        self.bench_one = Bench.objects.create(
            judgment=self.judgment,
            judge=self.legacy_judge_one,
        )
        self.bench_two = Bench.objects.create(
            judgment=self.judgment,
            judge=self.legacy_judge_two,
        )
        self.bench_three = Bench.objects.create(
            judgment=self.judgment,
            judge=self.legacy_judge_three,
            extracted_name="Manual extracted",
        )

    def test_command_backfills_legacy_judges_into_new_tables(self):
        call_command("backfill_judge_people")

        alias_one = JudgeAlias.objects.get(name="Abban JA")
        alias_two = JudgeAlias.objects.get(name="ABBAN, J.A.")
        alias_three = JudgeAlias.objects.get(name="Abban, J")

        self.assertEqual(1, JudgePerson.objects.count())
        self.assertEqual(3, JudgeAlias.objects.count())
        self.assertEqual(alias_one.judge_person_id, alias_two.judge_person_id)
        self.assertEqual(alias_one.judge_person_id, alias_three.judge_person_id)
        self.assertEqual("abban", alias_one.judge_person.full_name.casefold())
        self.assertEqual("JA", alias_one.title)
        self.assertEqual("JA", alias_two.title)
        self.assertEqual("J", alias_three.title)

        self.bench_one.refresh_from_db()
        self.bench_two.refresh_from_db()
        self.bench_three.refresh_from_db()

        self.assertEqual(alias_one.judge_person_id, self.bench_one.judge_person_id)
        self.assertEqual(alias_one.pk, self.bench_one.matched_alias_id)
        self.assertEqual("Abban JA", self.bench_one.extracted_name)

        self.assertEqual(alias_one.judge_person_id, self.bench_two.judge_person_id)
        self.assertEqual(alias_two.pk, self.bench_two.matched_alias_id)
        self.assertEqual("ABBAN, J.A.", self.bench_two.extracted_name)

        self.assertEqual(alias_three.judge_person_id, self.bench_three.judge_person_id)
        self.assertEqual(alias_three.pk, self.bench_three.matched_alias_id)
        self.assertEqual("Manual extracted", self.bench_three.extracted_name)

    def test_command_is_safe_to_run_twice(self):
        call_command("backfill_judge_people")
        call_command("backfill_judge_people")

        self.assertEqual(1, JudgePerson.objects.count())
        self.assertEqual(3, JudgeAlias.objects.count())

    def test_command_reuses_existing_case_insensitive_judge_person(self):
        existing = JudgePerson.objects.create(
            full_name="ABBAN",
            slug="abban-existing",
        )

        call_command("backfill_judge_people")

        self.assertEqual(1, JudgePerson.objects.count())
        self.assertEqual(existing.pk, JudgePerson.objects.get().pk)

    def test_dry_run_shows_canonical_person_and_alias_mappings(self):
        out = StringIO()

        call_command("backfill_judge_people", "--dry-run", stdout=out)

        output = out.getvalue()

        self.assertIn("JudgePerson(full_name='Abban')", output)
        self.assertIn(
            "JudgeAlias(name='Abban JA', normalized_name='abban ja', title='JA')",
            output,
        )
        self.assertIn("matched_alias='Abban JA', extracted_name='Abban JA'", output)
        self.assertIn(
            "JudgeAlias(name='ABBAN, J.A.', normalized_name='abban ja', title='JA')",
            output,
        )
        self.assertIn(
            "JudgeAlias(name='Abban, J', normalized_name='abban j', title='J')",
            output,
        )

    def test_command_groups_jsc_and_other_titles_under_one_canonical_judge(self):
        Judge.objects.create(name="Acquah, CJ")
        Judge.objects.create(name="Acquah, JSC")

        call_command("backfill_judge_people")

        acquah_cj = JudgeAlias.objects.get(name="Acquah, CJ")
        acquah_jsc = JudgeAlias.objects.get(name="Acquah, JSC")

        self.assertEqual(acquah_cj.judge_person_id, acquah_jsc.judge_person_id)
        self.assertEqual("Acquah", acquah_cj.judge_person.full_name)
        self.assertEqual("CJ", acquah_cj.title)
        self.assertEqual("JSC", acquah_jsc.title)


@override_settings(PEACHJAM=CANONICAL_JUDGE_IDENTITY_SETTINGS)
class JudgeIdentityWorkflowAdminTests(TestCase):
    fixtures = ["tests/countries", "tests/courts", "tests/languages"]

    def setUp(self):
        self.admin_user = User.objects.create_user(
            username="judge-admin@example.com",
            email="judge-admin@example.com",
            password="password",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(self.admin_user)
        self.workflow_url = reverse("peachjam_judgeperson_workflow")
        self.target = JudgePerson.objects.create(full_name="Abban", slug="abban")
        self.duplicate = JudgePerson.objects.create(
            full_name="Abban duplicate",
            slug="abban-duplicate",
        )
        self.empty_judge_person = JudgePerson.objects.create(
            full_name="Unused judge person",
            slug="unused-judge-person",
        )
        self.alias_one = JudgeAlias.objects.create(
            judge_person=self.duplicate,
            name="Abban JA",
        )
        self.alias_two = JudgeAlias.objects.create(
            judge_person=self.duplicate,
            name="ABBAN, J.A.",
        )
        self.legacy_judge_one = Judge.objects.create(name="Abban JA")
        self.legacy_judge_two = Judge.objects.create(name="ABBAN, J.A.")
        self.judgment = Judgment.objects.create(
            language=Language.objects.get(pk="en"),
            court=Court.objects.first(),
            date=datetime.date(2024, 1, 3),
            jurisdiction=Country.objects.get(pk="ZA"),
            case_name="Abban v Republic",
        )
        self.bench_one = Bench.objects.create(
            judgment=self.judgment,
            judge=self.legacy_judge_one,
            judge_person=self.duplicate,
            matched_alias=self.alias_one,
            extracted_name="Abban JA",
        )
        self.bench_two = Bench.objects.create(
            judgment=self.judgment,
            judge=self.legacy_judge_two,
            judge_person=self.duplicate,
            matched_alias=self.alias_two,
            extracted_name="Manual extracted",
        )

    def test_workflow_page_loads(self):
        response = self.client.get(self.workflow_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Judge identity workflow")
        self.assertContains(response, "Alias connections")
        self.assertContains(response, "Judge people")
        self.assertContains(response, "Abban JA")

    def test_workflow_relinks_legacy_judges_and_moves_alias_ownership(self):
        response = self.client.post(
            self.workflow_url,
            {
                "action": "apply_identity_changes",
                "target_judge_person": str(self.target.pk),
                "target_full_name": "",
                "selected_aliases": [
                    str(self.alias_one.pk),
                    str(self.alias_two.pk),
                ],
                "q": "",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Moved 2 selected aliases")
        self.assertContains(response, "deleted 1 now-empty source judge people")
        self.assertFalse(JudgePerson.objects.filter(pk=self.duplicate.pk).exists())

        aliases = set(self.target.aliases.values_list("name", flat=True))
        self.assertEqual(aliases, {"Abban JA", "ABBAN, J.A."})

        self.bench_one.refresh_from_db()
        self.bench_two.refresh_from_db()

        alias_one = JudgeAlias.objects.get(
            judge_person=self.target,
            name="Abban JA",
        )
        alias_two = JudgeAlias.objects.get(
            judge_person=self.target,
            name="ABBAN, J.A.",
        )

        self.assertEqual(self.bench_one.judge_person_id, self.target.pk)
        self.assertEqual(self.bench_one.matched_alias_id, alias_one.pk)
        self.assertEqual(self.bench_one.extracted_name, "Abban JA")

        self.assertEqual(self.bench_two.judge_person_id, self.target.pk)
        self.assertEqual(self.bench_two.matched_alias_id, alias_two.pk)
        self.assertEqual(self.bench_two.extracted_name, "Manual extracted")

    def test_workflow_can_create_canonical_judge_from_selected_legacy_judges(self):
        response = self.client.post(
            self.workflow_url,
            {
                "action": "apply_identity_changes",
                "target_judge_person": "",
                "target_full_name": "",
                "selected_aliases": [str(self.alias_two.pk)],
                "q": "",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(JudgePerson.objects.filter(full_name="ABBAN").exists())
        self.assertTrue(JudgePerson.objects.filter(pk=self.duplicate.pk).exists())

        created_person = JudgePerson.objects.get(full_name="ABBAN")
        alias = JudgeAlias.objects.get(
            judge_person=created_person,
            name="ABBAN, J.A.",
        )

        self.bench_two.refresh_from_db()
        self.assertEqual(self.bench_two.judge_person_id, created_person.pk)
        self.assertEqual(self.bench_two.matched_alias_id, alias.pk)

    def test_workflow_can_rename_selected_target_judge_person(self):
        response = self.client.post(
            self.workflow_url,
            {
                "action": "apply_identity_changes",
                "target_judge_person": str(self.target.pk),
                "target_full_name": "Justice Abban",
                "q": "",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Renamed judge person")

        self.target.refresh_from_db()
        self.assertEqual(self.target.full_name, "Justice Abban")
        self.assertEqual(self.target.slug, "justice-abban")

    def test_workflow_can_move_aliases_and_rename_target_judge_person(self):
        response = self.client.post(
            self.workflow_url,
            {
                "action": "apply_identity_changes",
                "target_judge_person": str(self.target.pk),
                "target_full_name": "Justice Abban",
                "selected_aliases": [
                    str(self.alias_one.pk),
                    str(self.alias_two.pk),
                ],
                "q": "",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Moved 2 selected aliases")
        self.assertContains(response, 'renamed the judge person from "Abban"')
        self.assertFalse(JudgePerson.objects.filter(pk=self.duplicate.pk).exists())

        self.target.refresh_from_db()
        self.assertEqual(self.target.full_name, "Justice Abban")

        aliases = set(self.target.aliases.values_list("name", flat=True))
        self.assertEqual(aliases, {"Abban JA", "ABBAN, J.A."})

    def test_workflow_can_merge_selected_judge_people(self):
        response = self.client.post(
            self.workflow_url,
            {
                "action": "merge_judge_people",
                "selected_judge_people": [str(self.duplicate.pk)],
                "merge_target_judge_person": str(self.target.pk),
                "q": "",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Merged 1 selected judge people")
        self.assertFalse(JudgePerson.objects.filter(pk=self.duplicate.pk).exists())

        aliases = set(self.target.aliases.values_list("name", flat=True))
        self.assertEqual(aliases, {"Abban JA", "ABBAN, J.A."})

        self.bench_one.refresh_from_db()
        self.bench_two.refresh_from_db()
        self.assertEqual(self.bench_one.judge_person_id, self.target.pk)
        self.assertEqual(self.bench_two.judge_person_id, self.target.pk)

    def test_workflow_can_delete_selected_aliases_only(self):
        response = self.client.post(
            self.workflow_url,
            {
                "action": "delete_records",
                "delete_mode": "aliases",
                "selected_aliases": [str(self.alias_two.pk)],
                "q": "",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Deleted 1 aliases")
        self.assertTrue(JudgePerson.objects.filter(pk=self.duplicate.pk).exists())
        self.assertFalse(JudgeAlias.objects.filter(pk=self.alias_two.pk).exists())

        self.bench_two.refresh_from_db()
        self.assertEqual(self.bench_two.judge_person_id, self.duplicate.pk)
        self.assertIsNone(self.bench_two.matched_alias_id)

    def test_workflow_can_delete_selected_judge_people_only(self):
        response = self.client.post(
            self.workflow_url,
            {
                "action": "delete_records",
                "delete_mode": "judge_people",
                "selected_judge_people": [str(self.duplicate.pk)],
                "q": "",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Deleted 1 judge people")
        self.assertContains(response, "Deleted 2 aliases")
        self.assertContains(response, "Cleared 2 matched alias links")
        self.assertContains(response, "Cleared 2 judge person links")
        self.assertFalse(JudgePerson.objects.filter(pk=self.duplicate.pk).exists())
        self.assertFalse(JudgeAlias.objects.filter(pk=self.alias_one.pk).exists())
        self.assertFalse(JudgeAlias.objects.filter(pk=self.alias_two.pk).exists())

        self.bench_one.refresh_from_db()
        self.bench_two.refresh_from_db()
        self.assertIsNone(self.bench_one.judge_person_id)
        self.assertIsNone(self.bench_one.matched_alias_id)
        self.assertIsNone(self.bench_two.judge_person_id)
        self.assertIsNone(self.bench_two.matched_alias_id)

    def test_workflow_can_delete_aliases_and_judge_people_together(self):
        response = self.client.post(
            self.workflow_url,
            {
                "action": "delete_records",
                "delete_mode": "both",
                "selected_aliases": [str(self.alias_one.pk)],
                "selected_judge_people": [str(self.empty_judge_person.pk)],
                "q": "",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Deleted 1 aliases")
        self.assertContains(response, "Deleted 1 judge people")
        self.assertFalse(JudgeAlias.objects.filter(pk=self.alias_one.pk).exists())
        self.assertFalse(
            JudgePerson.objects.filter(pk=self.empty_judge_person.pk).exists()
        )

        self.bench_one.refresh_from_db()
        self.assertEqual(self.bench_one.judge_person_id, self.duplicate.pk)
        self.assertIsNone(self.bench_one.matched_alias_id)

    def test_workflow_requires_judge_people_selection_for_judge_delete(self):
        response = self.client.post(
            self.workflow_url,
            {
                "action": "delete_records",
                "delete_mode": "judge_people",
                "q": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Select at least one judge person to delete.",
        )
        self.assertTrue(JudgePerson.objects.filter(pk=self.duplicate.pk).exists())
