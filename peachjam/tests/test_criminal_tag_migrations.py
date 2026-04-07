import datetime
from importlib import import_module

from countries_plus.models import Country
from django.test import TestCase
from languages_plus.models import Language

from peachjam.models import (
    CaseTag,
    Court,
    Judgment,
    JudgmentOffence,
    Offence,
    OffenceTag,
    Work,
)

criminal_tag_migration = import_module(
    "peachjam.migrations.0289_normalize_criminal_tag_models"
)


class CriminalTagMigrationHelperTests(TestCase):
    fixtures = [
        "tests/countries",
        "tests/courts",
        "tests/languages",
    ]

    def setUp(self):
        self.work = Work.objects.create(
            title="Penal Code",
            frbr_uri="/akn/za/act/2001/1",
        )
        self.offence = Offence.objects.create(
            work=self.work,
            provision_eid="sec_296",
            code="ROB-296",
            title="Robbery with violence",
        )
        self.judgment = Judgment.objects.create(
            case_name="Migration test appeal",
            work=self.work,
            court=Court.objects.first(),
            date=datetime.date(2025, 1, 1),
            language=Language.objects.get(pk="en"),
            jurisdiction=Country.objects.get(pk="ZA"),
        )
        self.judgment_offence = JudgmentOffence.objects.create(
            judgment=self.judgment,
            offence=self.offence,
        )
        self.offence_tag_map = {
            tag.name: tag
            for tag in [
                OffenceTag.objects.get_or_create(name="weapon-capable")[0],
                OffenceTag.objects.get_or_create(name="inchoate")[0],
            ]
        }
        self.case_tag_map = {
            tag.name: tag
            for tag in [
                CaseTag.objects.get_or_create(name="weapon-used")[0],
                CaseTag.objects.get_or_create(name="group-offending")[0],
            ]
        }

    def test_offence_legacy_array_values_map_cleanly_to_offence_tags(self):
        matched_tags = criminal_tag_migration.get_matched_legacy_tags(
            [" Weapon-capable ", "inchoate", "weapon-capable", "", "unknown-tag"],
            self.offence_tag_map,
        )

        self.offence.tags.set(matched_tags)

        self.assertEqual(
            list(self.offence.tags.values_list("name", flat=True)),
            ["inchoate", "weapon-capable"],
        )

    def test_judgment_offence_legacy_array_values_map_cleanly_to_case_tags(self):
        matched_tags = criminal_tag_migration.get_matched_legacy_tags(
            [" weapon-used ", "group-offending", "weapon-used", "", "unknown-tag"],
            self.case_tag_map,
        )

        self.judgment_offence.tags.set(matched_tags)

        self.assertEqual(
            list(self.judgment_offence.tags.values_list("name", flat=True)),
            ["group-offending", "weapon-used"],
        )

    def test_normalize_legacy_tag_array_deduplicates_and_ignores_blanks(self):
        self.assertEqual(
            criminal_tag_migration.normalize_legacy_tag_array(
                [" Weapon-capable ", "", "weapon-capable", "inchoate", None]
            ),
            ["weapon-capable", "inchoate"],
        )
