from dataclasses import dataclass, field

from django.core.management.base import BaseCommand, CommandError
from lxml import html
from lxml.html import tostring
from openai import OpenAI
from pydantic import BaseModel, Field

from peachjam.models import CoreDocument, Offence, Work


class Command(BaseCommand):
    help = "Extract offences from AKN HTML/XML and upsert Offence records for a Work."

    def add_arguments(self, parser):
        parser.add_argument(
            "--frbr-uri",
            required=True,
            help="FRBR URI of the document to extract offences from (e.g. /akn/ke/act/1930/63).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show extracted offences without writing to the database.",
        )
        parser.add_argument(
            "--max-sections",
            type=int,
            default=50,
            help="Maximum number of sections to process.",
        )

    def handle(self, *args, **options):
        doc = self.get_document(options["frbr_uri"])
        if not doc.content_html_is_akn:
            raise CommandError("Document doesn't have akn html")
        akn_html = doc.content_html

        sections = self.split_into_sections(
            akn_html, max_sections=options["max_sections"]
        )

        all_extracted = []

        for section in sections:
            self.stdout.write(f"extracting section {section['eid']}")

            offences = self.extract_offences(section["html"], model=options["model"])
            all_extracted.extend(offences)

        if not all_extracted:
            self.stdout.write(self.style.WARNING("No offences extracted."))
            return

        self.stdout.write(f"Extracted {len(all_extracted)} offence(s).")

        for offence in all_extracted:
            self.stdout.write(
                f"- {offence.provision_eid}: {offence.title} [{offence.code}]"
            )

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run: no database changes made."))
            return

        created_count = 0
        updated_count = 0

        for offence in all_extracted:
            _, created = Offence.objects.update_or_create(
                work=doc.work,
                code=offence.code,
                defaults={
                    "provision_eid": offence.provision_eid,
                    "code": offence.code,
                    "title": offence.title,
                    "description": offence.description,
                    "elements": offence.elements,
                    "penalty": offence.penalty,
                },
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Created {created_count} offence(s), updated {updated_count} offence(s)."
            )
        )

    def get_document(self, frbr_uri: str) -> Work:
        try:
            return CoreDocument.objects.get(expression_frbr_uri=frbr_uri)
        except CoreDocument.DoesNotExist as exc:
            raise CommandError(f"Work not found for FRBR URI: {frbr_uri}") from exc

    def split_into_sections(
        self,
        akn_html: str,
        max_sections: int = 100,
        max_chars: int = 8000,
    ):
        root = html.fromstring(akn_html)

        # Find section-like provisions
        sections = root.xpath(".//section | .//article")

        results = []

        for section in sections:
            if len(results) >= max_sections:
                break

            eid = section.get("eId")
            if not eid:
                continue

            section_html = tostring(
                section,
                encoding="unicode",
                with_tail=False,
            )

            # Skip oversized sections (don’t truncate legal text)
            if len(section_html) > max_chars:
                continue

            results.append(
                {
                    "eid": eid,
                    "html": section_html,
                }
            )

        return results

    def system_prompt(self):

        SYSTEM_PROMPT = """
        You extract offence definitions from Akoma Ntoso XML/HTML snippets for criminal codes.
        Return only offences that are clearly defined by the provided content.
        If none are defined, return an empty offences list.

        For each offence:
        - provision_eid: the closest provision id/eId (for example sec_296)
        - code: a short stable identifier if present, otherwise derive from provision number/title
        - title: offence name
        - description: concise summary of the prohibited conduct
        - elements: list of key legal elements required to prove the offence
        - penalty: punishment text if present

        Rules:
        - Never invent provision ids or penalties.
        - If a field is missing in the source, use an empty string (or empty list for elements).
        - Keep extracted text concise and factual.
        """.strip()

        return SYSTEM_PROMPT

    def extract_offences(self, akn_html, model="gpt-5-mini"):
        @dataclass
        class ExtractedOffence:
            provision_eid: str
            code: str
            title: str
            description: str = ""
            elements: list[str] = field(default_factory=list)
            penalty: str = ""

        class OffenceExtractionItem(BaseModel):
            provision_eid: str = Field(min_length=1)
            code: str = Field(min_length=1)
            title: str = Field(min_length=1)
            description: str = ""
            elements: list[str] = Field(default_factory=list)
            penalty: str = ""

        class OffenceExtractionResult(BaseModel):
            offences: list[OffenceExtractionItem] = Field(default_factory=list)

        client = OpenAI()
        response = client.responses.parse(
            model=model,
            input=[
                {"role": "system", "content": self.system_prompt()},
                {
                    "role": "user",
                    "content": "Extract offences from this AKN HTML/XML content:\n\n"
                    + akn_html,
                },
            ],
            text_format=OffenceExtractionResult,
        )
        parsed = response.output_parsed or OffenceExtractionResult()
        return [ExtractedOffence(**offence.model_dump()) for offence in parsed.offences]
