"""One-off import of judgments from courdappelcommerceabidjan.org for the AfricanLII
Arbitration Hub.

Four Ninja Tables are scraped:
  - Arrêts de la Cour d'Appel de Commerce d'Abidjan          (table 1056)
  - Ordonnances de référés                                    (table 1154)
  - Ordonnances de défense à exécution                        (table 1156)
  - Ordonnances sur requête                                   (table 1272)

A Scrapy spider crawls the site: it first fetches each listing page to extract
a fresh nonce, then hits the Ninja Tables AJAX endpoint to get all rows, and
finally downloads the PDF attached to each row.  Harvested data is handed back
to the Django management command, which saves Judgment records.

If a judgment with the same metadata_json.source_id already exists it is
skipped, so the command is safe to re-run.

Usage:
    python manage.py import_courdappelcommerceabidjan
    python manage.py import_courdappelcommerceabidjan --dry-run
    python manage.py import_courdappelcommerceabidjan --table 1056 --limit 10
    python manage.py import_courdappelcommerceabidjan --skip-pdfs
"""

import html
import os
import re
from datetime import datetime
from mimetypes import guess_extension
from tempfile import NamedTemporaryFile

import magic
import scrapy
from countries_plus.models import Country
from django.core.files import File
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from languages_plus.models import Language
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from peachjam.helpers import pdfjs_to_text
from peachjam.models import CaseNumber, Court, CourtClass, Judge, Judgment, SourceFile

BASE_URL = "https://courdappelcommerceabidjan.org"
AJAX_URL = f"{BASE_URL}/wp-admin/admin-ajax.php"

COURT_NAME = "Cour d'Appel de Commerce d'Abidjan"
COURT_CODE = "ci-caca"
COUNTRY_CODE = "CI"
LANGUAGE_CODE = "fr"

# Each entry describes one Ninja Tables table and how to map its fields.
TABLES = [
    {
        "id": 1056,
        "label": "Arrêts",
        "page_url": f"{BASE_URL}/arrets-de-la-cour-dappel-de-commerce-dabidjan/",
        "case_name_field": "documents",
        "rg_field": "rg",
        "date_field": "date_de_creation",
        "download_field": "telechargement",
        "outcome_field": "resultats",
    },
    {
        "id": 1154,
        "label": "Ordonnances de référés",
        "page_url": f"{BASE_URL}/ordonnances-de-referes/",
        "case_name_field": "affaires",
        "rg_field": "rg",
        "date_field": "date_ordonnance",
        "download_field": "download",
        "outcome_field": "resultats",
    },
    {
        "id": 1156,
        "label": "Ordonnances de défense à exécution",
        "page_url": f"{BASE_URL}/ordonnances-de-defense-a-execution/",
        "case_name_field": "affaires",
        "rg_field": "rg",
        "date_field": "date_ordonnance",
        "download_field": "download",
        "outcome_field": "resultats",
    },
    {
        "id": 1272,
        "label": "Ordonnances sur requête",
        "page_url": f"{BASE_URL}/ordonnances-sur-requete/",
        "case_name_field": "objet_requete",
        "rg_field": "n_requete",
        "date_field": "date_ordonnance",
        "download_field": "telechargement",
        "outcome_field": "decisions",
    },
]


# ---------------------------------------------------------------------------
# Scrapy items
# ---------------------------------------------------------------------------


class JudgmentItem(scrapy.Item):
    source_id = scrapy.Field()
    table_id = scrapy.Field()
    table_label = scrapy.Field()
    case_name = scrapy.Field()
    rg = scrapy.Field()
    date_str = scrapy.Field()
    outcome = scrapy.Field()
    download_url = scrapy.Field()
    pdf_content = scrapy.Field()  # raw bytes, populated after PDF download
    pdf_mimetype = scrapy.Field()


# ---------------------------------------------------------------------------
# Scrapy spider
# ---------------------------------------------------------------------------


class CourdappelSpider(scrapy.Spider):
    name = "courdappelcommerceabidjan"

    def __init__(self, tables, skip_pdfs=False, limit=None, **kwargs):
        super().__init__(**kwargs)
        self.tables = tables
        self.skip_pdfs = skip_pdfs
        self.limit = limit

    def start_requests(self):
        """Kick off by fetching each listing page to obtain a fresh nonce."""
        for table in self.tables:
            yield scrapy.Request(
                table["page_url"],
                callback=self._parse_nonce,
                cb_kwargs={"table": table},
            )

    def _parse_nonce(self, response, table):
        """Extract the WordPress nonce and request the AJAX data endpoint."""
        match = re.search(r"ninja_table_public_nonce=([a-f0-9]+)", response.text)
        if not match:
            self.logger.error(
                f"Could not find nonce on {response.url} — skipping table {table['id']}"
            )
            return
        nonce = match.group(1)
        self.logger.info(f"Table {table['id']}: nonce={nonce}")

        ajax_url = (
            f"{AJAX_URL}?action=wp_ajax_ninja_tables_public_action"
            f"&table_id={table['id']}&target_action=get-all-data"
            f"&default_sorting=new_first&skip_rows=0&limit_rows=0"
            f"&ninja_table_public_nonce={nonce}&chunk_number=0"
        )
        yield scrapy.Request(
            ajax_url,
            callback=self._parse_table,
            cb_kwargs={"table": table},
        )

    def _parse_table(self, response, table):
        """Parse the AJAX JSON response and yield one item per row."""
        rows = response.json()
        if self.limit:
            rows = rows[: self.limit]

        self.logger.info(f"Table {table['id']} ({table['label']}): {len(rows)} rows")

        for row in rows:
            value = row.get("value", row)
            item = self._build_item(value, table)
            if item is None:
                continue

            if self.skip_pdfs or not item["download_url"]:
                yield item
            else:
                yield scrapy.Request(
                    item["download_url"],
                    callback=self._parse_pdf,
                    cb_kwargs={"item": item},
                    dont_filter=True,
                )

    @staticmethod
    def _clean_case_name(raw):
        """Decode HTML entities, strip HTML tags, and remove list-number prefixes.

        The Ninja Tables API occasionally returns case names with:
          - HTML entities  e.g. "Société A &amp; Société B"
          - Embedded HTML  e.g. "<p><a href=...>...</a></p> (RG …)"
          - List prefixes  e.g. "1°- Party A  2°- Party B"
        """
        name = html.unescape(raw)
        name = re.sub(r"<[^>]+>", "", name)
        # Remove list-number prefixes: "1°-", "1° -", "1°)", "1°/", "1-", "01-", "1. "
        # but preserve things like "360°" (3-digit measurement) and case refs like "131-/2024".
        name = re.sub(r"(^|(?<=\s))\d+\s*°\s*[-)/]\s*", r"\1", name)
        name = re.sub(r"(^|(?<=\s))\d+-(?=[\s\w])", r"\1", name)
        name = re.sub(r"(^|(?<=\s))\d+\.\s+", r"\1", name)
        name = re.sub(r"(^|(?<=\s))\d{1,2}°\s+", r"\1", name)
        return name.strip()

    def _build_item(self, value, table):
        source_id = f"{table['id']}_{value.get('___id___', '')}"
        case_name = self._clean_case_name(value.get(table["case_name_field"]) or "")
        rg = (value.get(table["rg_field"]) or "").strip()
        date_str = (value.get(table["date_field"]) or "").strip()
        download_html = value.get(table["download_field"], "")
        outcome = (value.get(table["outcome_field"]) or "").strip()

        if not case_name:
            case_name = rg or source_id

        download_url = None
        if download_html:
            m = re.search(r'href=["\']([^"\']+)["\']', download_html)
            if m:
                download_url = m.group(1)

        return JudgmentItem(
            source_id=source_id,
            table_id=table["id"],
            table_label=table["label"],
            case_name=case_name,
            rg=rg,
            date_str=date_str,
            outcome=outcome,
            download_url=download_url,
            pdf_content=None,
            pdf_mimetype=None,
        )

    def _parse_pdf(self, response, item):
        """Attach the downloaded PDF bytes to the item."""
        item["pdf_content"] = response.body
        item["pdf_mimetype"] = (
            response.headers.get("Content-Type", b"application/pdf")
            .decode()
            .split(";")[0]
            .strip()
        )
        yield item


# ---------------------------------------------------------------------------
# Django management command
# ---------------------------------------------------------------------------


class Command(BaseCommand):
    help = (
        "One-off import of judgments from courdappelcommerceabidjan.org "
        "for the AfricanLII Arbitration Hub (uses Scrapy)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be imported without writing to the database.",
        )
        parser.add_argument(
            "--table",
            type=int,
            choices=[t["id"] for t in TABLES],
            help="Only import from the specified table ID.",
        )
        parser.add_argument(
            "--skip-pdfs",
            action="store_true",
            help="Skip downloading and attaching PDFs.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Limit the number of records imported per table (useful for testing).",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        skip_pdfs = options["skip_pdfs"]
        limit = options["limit"]
        table_filter = options.get("table")

        tables = (
            TABLES
            if not table_filter
            else [t for t in TABLES if t["id"] == table_filter]
        )

        # ------------------------------------------------------------------
        # 1. Run the Scrapy spider and collect all items.
        # ------------------------------------------------------------------
        collected_items = []

        settings = get_project_settings()
        settings.update(
            {
                "LOG_LEVEL": "INFO",
                "ROBOTSTXT_OBEY": False,
                # Be polite — one request at a time with a small delay.
                "CONCURRENT_REQUESTS": 4,
                "DOWNLOAD_DELAY": 0.5,
                # Disable the default Scrapy item pipelines; we collect manually.
                "ITEM_PIPELINES": {},
            }
        )

        process = CrawlerProcess(settings)

        def _collect(item, response, spider):
            collected_items.append(dict(item))

        from scrapy import signals
        from scrapy.signalmanager import dispatcher

        dispatcher.connect(_collect, signal=signals.item_scraped)

        process.crawl(
            CourdappelSpider,
            tables=tables,
            skip_pdfs=skip_pdfs,
            limit=limit,
        )
        process.start()  # blocks until the spider finishes

        self.stdout.write(f"\nSpider finished. {len(collected_items)} items collected.")

        if dry_run:
            for item in collected_items:
                self.stdout.write(
                    f"  [DRY RUN] {item['case_name'][:80]} | {item['rg']} "
                    f"| {item['date_str']} | PDF: {item['download_url']}"
                )
            self.stdout.write(f"\nDry run complete: {len(collected_items)} items.")
            return

        # ------------------------------------------------------------------
        # 2. Resolve shared Django objects once.
        # ------------------------------------------------------------------
        jurisdiction = Country.objects.get(iso=COUNTRY_CODE)
        language = Language.objects.get(iso_639_1=LANGUAGE_CODE)
        court = self._get_or_create_court(jurisdiction)

        # ------------------------------------------------------------------
        # 3. Persist each item.
        # ------------------------------------------------------------------
        total_created = 0
        total_skipped = 0
        total_errors = 0

        for item in collected_items:
            try:
                created = self._save_item(item, court, jurisdiction, language)
                if created:
                    total_created += 1
                else:
                    total_skipped += 1
            except Exception as e:
                self.stderr.write(f"  ERROR [{item['source_id']}]: {e}")
                total_errors += 1

        self.stdout.write(
            f"\nImport complete: {total_created} created, "
            f"{total_skipped} skipped, {total_errors} errors"
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_or_create_court(self, jurisdiction):
        court_class, _ = CourtClass.objects.get_or_create(
            slug="commercial-courts",
            defaults={"name": "Commercial Courts", "order": 10},
        )
        court, created = Court.objects.get_or_create(
            code=COURT_CODE,
            defaults={
                "name": COURT_NAME,
                "court_class": court_class,
                "country": jurisdiction,
            },
        )
        if created:
            self.stdout.write(f"Created court: {court}")
        return court

    def _parse_date(self, date_str):
        if not date_str:
            return None
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(date_str.strip(), fmt).date()
            except ValueError:
                continue
        self.stderr.write(f"  Could not parse date: {date_str!r}")
        return None

    def _save_item(self, item, court, jurisdiction, language):
        source_id = item["source_id"]

        parsed_date = self._parse_date(item["date_str"])
        if not parsed_date:
            self.stdout.write(
                f"  SKIP [{source_id}]: invalid date {item['date_str']!r}"
            )
            return False

        if Judgment.objects.filter(metadata_json__source_id=source_id).exists():
            self.stdout.write(f"  SKIP [{source_id}]: already imported")
            return False

        judgment = Judgment(
            case_name=item["case_name"],
            date=parsed_date,
            court=court,
            jurisdiction=jurisdiction,
            language=language,
            published=True,
            metadata_json={
                "source_id": source_id,
                "table_id": item["table_id"],
                "table_label": item["table_label"],
                "rg": item["rg"],
                "outcome": item["outcome"],
            },
        )
        judgment.save()

        if item["rg"]:
            CaseNumber.objects.create(
                document=judgment,
                string_override=item["rg"],
            )
            # Re-save so assign_title() picks up the new case number.
            judgment.save()

        if item.get("pdf_content"):
            judges = self._extract_judges_from_pdf(item["pdf_content"])
            for name in judges:
                judge, _ = Judge.objects.get_or_create(name=name)
                judgment.judges.add(judge)

            self._attach_pdf(judgment, item)

        judgment.update_text_content()
        self.stdout.write(f"  CREATED [{source_id}]: {judgment.title[:80]}")
        return True

    def _extract_judges_from_pdf(self, pdf_bytes):
        """Write PDF bytes to a temp file, extract text, and return a list of judge names."""
        with NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(pdf_bytes)
            fname = f.name
        try:
            text = pdfjs_to_text(fname)
            return self._parse_judges(text)
        except Exception as e:
            self.stderr.write(f"  Could not extract judges from PDF: {e}")
            return []
        finally:
            os.unlink(fname)

    def _parse_judges(self, text):
        """Extract judge names from court decision text.

        Handles two formats found in these documents:

        1. Collegiate bench (arrêts and ordonnances de référés):
              à laquelle siégeaient :
              Docteur KOMOIN François, Premier Président ... ;
              Madame ASSI Eunice épouse AYIE, TALL Yacouba, ... Conseillers ... ;
              Avec l'assistance de ...

        2. Single-judge ordonnances:
              Nous, KACOU Brédoumou Florent, Conseiller ...
        """
        # Normalise whitespace so patterns aren't broken by line-wrapping.
        text = re.sub(r"\s+", " ", text)

        # --- Pattern 1: collegiate bench ---
        m = re.search(
            r"siégeaient\s*:(.*?)Avec\s+l.assistance",
            text,
            re.IGNORECASE,
        )
        if m:
            return self._parse_collegiate_bench(m.group(1))

        # --- Pattern 2: single-judge ordonnance ---
        m = re.search(
            r"Nous,\s+(.+?),\s+(?:Conseiller|Premier\s+Président)",
            text,
            re.IGNORECASE,
        )
        if m:
            name = self._clean_name(m.group(1))
            return [name] if name else []

        return []

    def _parse_collegiate_bench(self, section):
        """Parse the text between 'siégeaient :' and 'Avec l'assistance'."""
        names = []
        # Each semicolon-delimited clause describes one judge or a group of judges.
        for clause in section.split(";"):
            clause = clause.strip()
            if not clause:
                continue

            # Strip the role description that follows the name(s).
            clause = re.sub(
                r",?\s*(Premier\s+Président\b.*|Conseillers?\s+à\b.*|Membres?\b.*)",
                "",
                clause,
                flags=re.IGNORECASE,
            ).strip()

            # Remove honorific prefixes so they don't become part of the name.
            clause = re.sub(
                r"\b(Docteur|Dr\.?|Madame|Mme\.?|Monsieur|M\.?|messieurs|Maître|Me\.?)\b",
                "",
                clause,
                flags=re.IGNORECASE,
            )

            # Split multiple names within the same clause on "et" or commas.
            for part in re.split(r"\bet\b|,", clause):
                name = self._clean_name(part)
                if name:
                    names.append(name)

        return names

    def _clean_name(self, raw):
        """Strip stray punctuation and whitespace; return None if too short to be a name."""
        name = raw.strip(" ,;.")
        name = re.sub(r"\s+", " ", name)
        # Require at least two whitespace-separated tokens (first + last name).
        if len(name.split()) < 2:
            return None
        return name

    def _attach_pdf(self, judgment, item):
        with NamedTemporaryFile(suffix=".pdf") as f:
            f.write(item["pdf_content"])
            f.flush()
            mimetype = magic.from_file(f.name, mime=True)
            ext = guess_extension(mimetype) or ".pdf"
            filename = f"{slugify(item['case_name'])[:150]}{ext}"
            sf, _ = SourceFile.objects.update_or_create(
                document=judgment,
                defaults={
                    "file": File(f, filename),
                    "mimetype": mimetype,
                },
            )
            sf.ensure_file_as_pdf()
