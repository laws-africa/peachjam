import re
from dataclasses import dataclass, field

from django.core.management.base import BaseCommand, CommandError
from lxml import html
from lxml.html import tostring
from openai import OpenAI
from pydantic import BaseModel, Field

from peachjam.models import CoreDocument, Offence


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
            default=1000,
            help="Maximum number of sections to process.",
        )

    # ----------------------------
    # Main entry point
    # ----------------------------
    def handle(self, *args, **options):
        doc = self.get_document(options["frbr_uri"])
        if not doc.content_html_is_akn:
            raise CommandError("Document doesn't have akn html")

        akn_html = doc.content_html
        sections = self.split_into_sections(
            akn_html, max_sections=options["max_sections"]
        )

        all_extracted = []
        created_count = 0
        updated_count = 0

        for section in sections:
            eid = section["eid"]
            self.stdout.write(f"Extracting section {eid}")

            offences = self.extract_offences(
                akn_html=section["html"],
                allowed_eids=section["allowed_eids"],
                section_context=section["context"],
            )

            if offences:
                self.stdout.write(f"  Found {len(offences)} offence(s) in {eid}")
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

    # ----------------------------
    # Document retrieval
    # ----------------------------
    def get_document(self, frbr_uri: str):
        try:
            return CoreDocument.objects.get(expression_frbr_uri=frbr_uri)
        except CoreDocument.DoesNotExist as exc:
            raise CommandError(f"Work not found for FRBR URI: {frbr_uri}") from exc

    # ----------------------------
    # Section selection + cleaning
    # ----------------------------
    OFFENCE_CUES_RE = re.compile(
        r"\b("
        r"commits?\s+(an\s+)?offence"
        r"|commits?\s+the\s+offence\s+of\s+[a-z][a-z\s-]{0,60}"
        r"|is\s+guilty\s+of\s+an?\s+offence"
        r"|shall\s+be\s+guilty"
        r"|it\s+is\s+an?\s+offence\s+(for\s+[^.]{0,80}\s+)?to"  # NEW
        r"|is\s+an?\s+offence\s+(for\s+[^.]{0,80}\s+)?to"  # NEW
        r")\b",
        re.IGNORECASE,
    )

    def split_into_sections(
        self, akn_html: str, max_sections: int = 1000, max_chars: int = 8000
    ):
        """
        Improvements vs original:
        - Only targets akn-section nodes (skips chapter/part containers).
        - Skips clearly non-substantive sections (repealed/omitted, etc.).
        - Strips editorial/annotation noise before sending to the model.
        - Avoids API calls when a section has no offence cues.
        - Passes allowed data-eid list to validate model output deterministically.
        """
        root = html.fromstring(akn_html)

        # Prefer "real" provisions: sections only (articles optional if your content uses them)
        nodes = root.xpath(
            ".//section[contains(concat(' ', normalize-space(@class), ' '), ' akn-section ')]"
            " | .//article[contains(concat(' ', normalize-space(@class), ' '), ' akn-article ')]"
        )

        results = []
        for node in nodes:
            if len(results) >= max_sections:
                break

            eid = node.get("data-eid")
            if not eid:
                continue

            # Extract heading for skip logic / context
            heading_text = self._extract_heading_text(node)

            # Skip obvious non-provisions
            if self._should_skip_section(node, heading_text):
                continue

            # Clone & clean
            cleaned_node = self._clone_node(node)
            self._strip_unnecessary_akn_markup(cleaned_node)

            section_html = tostring(cleaned_node, encoding="unicode", with_tail=False)
            if len(section_html) > max_chars:
                # Skip oversized sections; do not truncate legal text
                continue

            # If no offence cues, skip to reduce false positives + cost
            plain = self._plain_text(cleaned_node)
            if not self.OFFENCE_CUES_RE.search(plain):
                continue

            allowed_eids = self._collect_data_eids(cleaned_node)

            results.append(
                {
                    "eid": eid,
                    "context": {"heading": heading_text},
                    "allowed_eids": allowed_eids,
                    "html": section_html,
                }
            )

        return results

    def _extract_heading_text(self, node) -> str:
        # Common AKN heading structure: <h3>39. Treason</h3>
        h = node.xpath(".//*[self::h1 or self::h2 or self::h3][1]")
        if not h:
            return ""
        return " ".join(h[0].itertext()).strip()

    def _should_skip_section(self, node, heading_text: str) -> bool:
        ht = (heading_text or "").strip().lower()
        if not ht:
            # If there is no heading, don’t auto-skip; rely on cue detection later
            return False

        # Skip by heading keyword
        if any(k in ht for k in ["repealed", "omitted"]):
            return True

        # Skip pure definition/interpretation style sections by heading (you can extend this list)
        if ht.startswith("definition of "):
            return True

        # Some AKN puts “[Omitted.]” or similar in remarks
        remark_text = (
            " ".join(node.xpath(".//*[contains(@class,'akn-remark')]//text()"))
            .strip()
            .lower()
        )
        if "[omitted" in remark_text or "[repealed" in remark_text:
            return True

        return False

    def _clone_node(self, node):
        # tostring -> fromstring to get a detached copy we can safely mutate
        return html.fromstring(tostring(node, encoding="unicode", with_tail=False))

    def _strip_unnecessary_akn_markup(self, node):
        """
        Remove editorial/annotation noise while preserving visible legal text.
        """
        # Remove editorial remarks + authorial notes completely (typically citations/history)
        for el in node.xpath(
            ".//*[contains(@class,'akn-remark') or contains(@class,'akn-authorialNote')]"
        ):
            el.drop_tree()

        # Turn references into plain text (keep the visible text, remove the link wrapper)
        for a in node.xpath(".//a[contains(@class,'akn-ref')]"):
            # Keep its text content in place, remove tag
            a.drop_tag()

        # Keep term spans (they usually don't hurt), but remove UI-ish attributes to reduce noise
        for el in node.xpath(".//*[@data-refersto or @aria-expanded]"):
            if "data-refersto" in el.attrib:
                del el.attrib["data-refersto"]
            if "aria-expanded" in el.attrib:
                del el.attrib["aria-expanded"]

        # Strip bulky attributes that don’t help extraction
        for el in node.xpath(".//*[@id or @data-href]"):
            if "id" in el.attrib:
                del el.attrib["id"]
            if "data-href" in el.attrib:
                del el.attrib["data-href"]

        # IMPORTANT: keep @data-eid exactly as-is (we rely on it)
        # Also keep basic structure tags; do not flatten.

    def _collect_data_eids(self, node) -> list[str]:
        eids = []
        for el in node.xpath(".//*[@data-eid]"):
            v = el.get("data-eid")
            if v:
                eids.append(v)
        # Preserve order, unique
        seen = set()
        out = []
        for v in eids:
            if v in seen:
                continue
            seen.add(v)
            out.append(v)
        return out

    def _plain_text(self, node) -> str:
        return " ".join(" ".join(node.itertext()).split()).strip()

    # ----------------------------
    # Prompting
    # ----------------------------
    def system_prompt(self) -> str:
        return """
You extract criminal offence definitions from Akoma Ntoso (AKN) HTML/XML snippets.

Return JSON matching the provided schema:
{ "offences": [ { provision_eid, code, title, description, elements, penalty } ] }

Core task
- Identify ONLY provisions that CREATE an offence
    (i.e., the text states that a person “commits an offence”,
    “commits treason”, “is guilty of an offence”, “shall be guilty”, etc.).
- Do NOT return definitions, interpretive rules, procedural requirements, defenses, consent-to-prosecute rules,
or repealed/omitted provisions unless they also explicitly create an offence.

What counts as an offence
Include a record when the provision explicitly criminalises conduct, e.g.:
- “commits treason …”
- “commits an offence …”
- “shall be guilty of an offence …”
- “shall be liable to …” ONLY when tied to prohibited conduct in the same provision.

Exclude (do NOT output an offence) when the section is purely:
- definitional / interpretive (e.g. “Definition of …”, “... is deemed to ...”)
- “Omitted”, “Repealed”
- procedural (e.g. consent to prosecute)
- defensive (e.g. “... as defence ...”) unless it ALSO defines an offence.
- only discusses the punishment for an offence, defined in another section

Provision ID rules (VERY IMPORTANT)
- provision_eid MUST be copied from an existing @data-eid value in the snippet.
- Choose the most specific @data-eid that contains the offence-creating clause
(“commits … / offence … / guilty … / liable …”).
- Never invent or simplify eIds. Use the exact string.

How many offences
- Default: 1 offence per section heading (the <h3> title), even if it lists multiple alternative ways to commit it.
- Emit multiple offences ONLY if there are clearly separate offence-creating clauses that criminalise different conduct
and should be separate records (e.g., distinct “commits an offence … shall be liable …” blocks).
- If you emit multiple offences from one section, make codes deterministic with suffixes (_a, _b, _c).

Penalty rules
- Penalty must be copied or closely paraphrased from the snippet (no guessing).
- If the penalty is in a different subsection within the SAME section, combine it into the same offence record.
- If no penalty is present, return "".

Title rules
- Use the section heading text as the title when it is specific (e.g. “Treason”).
- Do not include the numbering of the heading
- If the heading is generic, create a precise title from the offence clause.
- Do not use “Omitted” or “Repealed” as a title.

Code rules (stable identifier)
- Derive code deterministically from the provision_eid:
  - Prefer a section-based id like sec_39 (or sec_63C) if it appears in the provision_eid.
  - If needed for multiple offences in one section, extend deterministically (e.g. sec_48_a).
- Never include spaces; use lowercase letters, digits, underscores.

Description and elements
- description: 1–2 sentences summarising prohibited conduct (exclude penalty).
- elements: 2–7 concise strings reflecting legal elements supported by the snippet only.

Output discipline
- If unsure whether a provision creates an offence, omit it.
- If none are clearly defined, return { "offences": [] }.
""".strip()

    def build_user_prompt(
        self, akn_html: str, allowed_eids: list[str], section_context: dict
    ) -> str:
        heading = (section_context or {}).get("heading", "")
        allowed_preview = ", ".join(allowed_eids[:50])
        more = "" if len(allowed_eids) <= 50 else f" (+{len(allowed_eids) - 50} more)"

        return (
            "Extract offences from this AKN HTML/XML snippet.\n"
            "CRITICAL CONSTRAINTS:\n"
            f"- provision_eid MUST be exactly one of the @data-eid values that appear in the snippet.\n"
            f"- Allowed data-eid values (partial): {allowed_preview}{more}\n"
            "- Return JSON only.\n\n"
            f"Section heading (context): {heading}\n\n"
            "AKN snippet:\n"
            f"{akn_html}"
        )

    # ----------------------------
    # Extraction + validation
    # ----------------------------
    def extract_offences(
        self,
        akn_html: str,
        allowed_eids: list[str],
        section_context: dict,
        model="gpt-5-mini",
    ):
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
                    "content": self.build_user_prompt(
                        akn_html, allowed_eids, section_context
                    ),
                },
            ],
            text_format=OffenceExtractionResult,
        )

        parsed = response.output_parsed or OffenceExtractionResult()
        offences = [ExtractedOffence(**o.model_dump()) for o in parsed.offences]

        # Deterministic hardening:
        # 1) Drop anything whose provision_eid is not literally in the snippet
        allowed = set(allowed_eids)
        offences = [o for o in offences if o.provision_eid in allowed]

        # 2) Normalize/repair code deterministically from provision_eid (keeps runs stable)
        for o in offences:
            o.code = self._derive_code_from_eid(o.provision_eid, fallback=o.code)

        # 3) Deduplicate by code within a run (prefer richer record)
        offences = self._dedupe_offences(offences)

        return offences

    def _derive_code_from_eid(self, provision_eid: str, fallback: str) -> str:
        """
        Produces a stable code like:
        - sec_39
        - sec_63c
        - sec_48_para_a  (only if no better match)
        """
        eid = provision_eid or ""
        # Look for "__sec_XX" patterns (including 63C, 63B etc.)
        m = re.search(r"__sec_([0-9]+[A-Za-z]?)\b", eid)
        if m:
            return f"sec_{m.group(1).lower()}"

        # Some AKN uses "...__art_..."
        m = re.search(r"__art_([0-9]+[A-Za-z]?)\b", eid)
        if m:
            return f"art_{m.group(1).lower()}"

        # As a fallback, compress the eid safely
        compact = re.sub(r"[^a-zA-Z0-9]+", "_", eid).strip("_").lower()
        if compact:
            return compact[:80]  # keep bounded

        # Last resort: keep model-provided (still validated by Pydantic)
        return re.sub(r"\s+", "_", (fallback or "").strip()).lower() or "offence"

    def _dedupe_offences(self, offences):
        def score(o):
            # prefer ones with penalty, more elements, and longer description (as proxy for completeness)
            return (
                1 if o.penalty else 0,
                len(o.elements or []),
                len(o.description or ""),
            )

        by_code = {}
        for o in offences:
            existing = by_code.get(o.code)
            if not existing or score(o) > score(existing):
                by_code[o.code] = o
        return list(by_code.values())
