import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from countries_plus.models import Country
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from languages_plus.models import Language

from peachjam.analysis.judgment_staging.schemas import (
    FieldConfidence,
    JudgmentExtractionLLMOutput,
    StagedJudgmentPayload,
    StagedJudgmentRecord,
)
from peachjam.analysis.judgment_staging.service import JudgmentStagingService
from peachjam.models import Court


class JudgmentStagingServiceTestCase(SimpleTestCase):
    @patch.dict(
        os.environ,
        {
            "OPENAI_API_KEY": "test-openai-key",
            "LANGFUSE_PUBLIC_KEY": "test-langfuse-public-key",
            "LANGFUSE_SECRET_KEY": "test-langfuse-secret-key",
        },
        clear=False,
    )
    @patch("peachjam.analysis.judgment_staging.service.langfuse.get_prompt")
    @patch("peachjam.analysis.judgment_staging.service.OpenAI")
    def test_extract_from_prepared_source_uses_structured_llm_output(
        self, openai_cls, get_prompt
    ):
        fake_payload = StagedJudgmentPayload(
            title="Foo v Bar [2024] TEST 1",
            case_name="Foo v Bar",
            date="2024-01-15",
            citation="[2024] TEST 1",
            mnc="[2024] TEST 1",
            court_name="Test Court",
            jurisdiction_code="ZA",
            language_code="eng",
        )
        fake_output = JudgmentExtractionLLMOutput(
            payload=fake_payload,
            confidence_by_field=[
                FieldConfidence(field_name="case_name", confidence="high"),
                FieldConfidence(field_name="date", confidence="high"),
            ],
            validation_errors=[],
        )
        fake_response = SimpleNamespace(output_parsed=fake_output)

        fake_openai = MagicMock()
        fake_openai.responses.parse.return_value = fake_response
        openai_cls.return_value = fake_openai

        fake_prompt = MagicMock()
        fake_prompt.compile.return_value = "Extract this judgment."
        fake_prompt.config = {"model": "gpt-5-mini", "version": 3}
        fake_prompt.version = "3"
        get_prompt.return_value = fake_prompt

        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "sample.pdf"
            pdf_path.write_bytes(b"%PDF-1.4 sample")

            service = JudgmentStagingService()
            prepared = service.prepare_pdf(pdf_path)
            result = service.extract_from_prepared_source(
                prepared,
                default_language="eng",
                default_jurisdiction="ZA",
                published=True,
                allow_robots=False,
            )

        self.assertEqual("Foo v Bar", result.record.payload.case_name)
        self.assertEqual("eng", result.record.payload.language_code)
        self.assertEqual("ZA", result.record.payload.jurisdiction_code)
        self.assertEqual("gpt-5-mini", result.record.extraction_model)
        self.assertEqual("3", result.record.prompt_version)
        self.assertFalse(result.record.needs_review)
        fake_openai.responses.parse.assert_called_once()
        parse_kwargs = fake_openai.responses.parse.call_args.kwargs
        self.assertEqual(JudgmentExtractionLLMOutput, parse_kwargs["text_format"])
        self.assertEqual(
            "sample.pdf", parse_kwargs["input"][0]["content"][1]["filename"]
        )
        self.assertTrue(
            parse_kwargs["input"][0]["content"][1]["file_data"].startswith(
                "data:application/pdf;base64,"
            )
        )

    @patch.dict(os.environ, {}, clear=True)
    def test_extract_requires_openai_key(self):
        service = JudgmentStagingService()
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "sample.pdf"
            pdf_path.write_bytes(b"%PDF-1.4 sample")
            prepared = service.prepare_pdf(pdf_path)
            with self.assertRaisesMessage(
                Exception, "OPENAI_API_KEY is not configured."
            ):
                service.extract_from_prepared_source(prepared)

    @patch.dict(
        os.environ,
        {
            "OPENAI_API_KEY": "test-openai-key",
        },
        clear=False,
    )
    @patch("peachjam.analysis.judgment_staging.service.OpenAI")
    def test_extract_command_writes_structured_jsonl(self, openai_cls):
        fake_payload = StagedJudgmentPayload(
            case_name="Sample v Example",
            title="Sample v Example",
            date="2024-02-01",
            jurisdiction_code="CI",
            language_code="fra",
        )
        fake_output = JudgmentExtractionLLMOutput(
            payload=fake_payload,
            confidence_by_field=[
                FieldConfidence(field_name="case_name", confidence="high")
            ],
            validation_errors=[],
        )
        fake_openai = MagicMock()
        fake_openai.responses.parse.return_value = SimpleNamespace(
            output_parsed=fake_output
        )
        openai_cls.return_value = fake_openai

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            pdf_path = base / "sample.pdf"
            pdf_path.write_bytes(b"%PDF-1.4 sample")
            prepared = base / "prepared.jsonl"
            extracted = base / "extracted.jsonl"

            call_command(
                "prepare_judgment_staging",
                str(base),
                output=str(prepared),
                limit=1,
            )
            call_command(
                "extract_judgment_staging_llm",
                str(prepared),
                output=str(extracted),
                default_language="fra",
                default_jurisdiction="CI",
            )

            rows = [
                json.loads(line)
                for line in extracted.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(1, len(rows))
            self.assertEqual("Sample v Example", rows[0]["payload"]["case_name"])


class JudgmentStagingImportTestCase(TestCase):
    fixtures = ["tests/courts", "tests/countries", "tests/languages"]

    def test_import_staged_record_uses_judgment_resource_and_attaches_pdf(self):
        service = JudgmentStagingService()
        country = Country.objects.get(pk="ZA")
        Language.objects.get(pk="en")
        court = Court.objects.create(
            name="Import test court",
            code="import-test-court",
            country=country,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "import-test.pdf"
            fixture_pdf = Path("peachjam/fixtures/tests/citations.pdf")
            pdf_path.write_bytes(fixture_pdf.read_bytes())

            prepared = service.prepare_pdf(pdf_path)
            record = StagedJudgmentRecord(
                source=prepared,
                payload=StagedJudgmentPayload(
                    title="Alpha v Beta [2024] import-test-court 1",
                    case_name="Alpha v Beta",
                    date="2024-01-15",
                    citation="[2024] import-test-court 1",
                    mnc="[2024] import-test-court 1",
                    court_name=court.name,
                    jurisdiction_code="ZA",
                    language_code="eng",
                    case_numbers=[
                        {
                            "string_override": "123/2024",
                            "number": 123,
                            "year": 2024,
                            "matter_type": "CIV",
                        }
                    ],
                    judges=["Judge One", "Judge Two"],
                    lower_court_judges=["Lower Judge"],
                    attorneys=["Attorney One"],
                    outcomes=["Dismissed"],
                    case_summary="Summary",
                    flynote="Flynote",
                    order="Order",
                    filing_year=2024,
                    published=True,
                    allow_robots=True,
                ),
                extraction_model="gpt-5-mini",
                prompt_name="extract/judgment-staging",
                prompt_version="1",
                raw_llm_output={},
                confidence_by_field=[],
                validation_errors=[],
                needs_review=False,
            )

            judgment = service.import_staged_record(record)

        judgment.refresh_from_db()
        self.assertEqual("Alpha v Beta", judgment.case_name)
        self.assertEqual("Summary", judgment.case_summary)
        self.assertEqual("Flynote", judgment.flynote)
        self.assertEqual("Order", judgment.order)
        self.assertEqual(2024, judgment.filing_year)
        self.assertTrue(judgment.published)
        self.assertTrue(judgment.allow_robots)
        self.assertEqual(court, judgment.court)
        self.assertEqual(1, judgment.case_numbers.count())
        self.assertEqual("123/2024", judgment.case_numbers.first().string_override)
        self.assertEqual(2, judgment.judges.count())
        self.assertEqual(1, judgment.lower_court_judges.count())
        self.assertEqual(1, judgment.attorneys.count())
        self.assertEqual(1, judgment.outcomes.count())
        self.assertTrue(hasattr(judgment, "source_file"))
        self.assertEqual("application/pdf", judgment.source_file.mimetype)
        self.assertEqual(prepared.source_sha256, judgment.source_file.sha256)
