"""Flynote text parsing and Flynote model synchronisation.

Judgments in Southern/East African legal databases carry a short structured
summary called a *flynote*.  Flynotes use dashes to express hierarchy and
semicolons to separate sibling branches::

    Criminal law — admissibility — trial within a trial;
    right to legal representation

This module converts that notation into paths and keeps the
Django ``Flynote`` / ``JudgmentFlynote`` tables in sync with each judgment's
flynote field.

Two classes are exposed:

* **FlynoteParser** – stateless text-to-paths converter.
* **FlynoteUpdater** – creates/reuses ``Flynote`` nodes and links
  them to a ``Judgment`` via ``JudgmentFlynote``.
"""

import logging
import re
from html import unescape
from time import perf_counter

from django.db import IntegrityError, transaction
from django.utils.text import slugify

from peachjam.models.flynote import Flynote, JudgmentFlynote
from peachjam.tasks import refresh_flynote_document_count

log = logging.getLogger(__name__)


class FlynoteParser:
    """Parses raw flynote text into structured paths.

    Handles dash/semicolon splitting and hierarchical path construction from
    legal flynote conventions.

    Usage::

        parser = FlynoteParser()
        paths = parser.parse(
            "Criminal law — admissibility — trial within a trial"
        )
        # paths == [['Criminal law', 'admissibility', 'trial within a trial']]
    """

    DASH_PATTERN = r"\s*[\u2014\u2013]\s*|\s+[-\u2010\u2011\u2012]\s+"
    MAX_NAME_LENGTH = 255
    HELD_PATTERN = re.compile(r"\bHeld:\s*", re.IGNORECASE)
    SENTENCE_BOUNDARY_PATTERN = re.compile(r"(?<=\.)\s+(?=[A-Z])")
    REPORT_MARKER_PATTERN = re.compile(
        r"^(?:[A-Z])\s+(?=[A-Z][^-–—]{1,80}(?:\s*[\u2014\u2013]\s*|\s+[-\u2010\u2011\u2012]\s+))"
    )
    TOPIC_RESTART_PATTERN = re.compile(
        r"(?P<phrase>[A-Z][A-Za-z/&'()]+(?:\s+[A-Za-z][A-Za-z/&'()]+){0,6})"
        r"(?:\s*[\u2014\u2013]\s*|\s+[-\u2010\u2011\u2012]\s+)"
    )
    EMBEDDED_TITLE_RESTART_PATTERN = re.compile(
        r"(?<=[a-z]\s)"
        r"(?P<phrase>[A-Z][A-Za-z/&'()]+(?:\s+[A-Z][A-Za-z/&'()]+){1,3})"
        r"(?:\s*[\u2014\u2013]\s*|\s+[-\u2010\u2011\u2012]\s+)"
    )
    EMBEDDED_SINGLE_TOPIC_PATTERN = re.compile(
        r"(?<=[a-z]\s)"
        r"(?P<phrase>[A-Z][A-Za-z/&'()]+)"
        r"(?:\s*[\u2014\u2013]\s*|\s+[-\u2010\u2011\u2012]\s+)"
    )
    EMBEDDED_SINGLE_TOPIC_WORDS = {
        "Appeal",
        "Arbitration",
        "Bail",
        "Costs",
        "Damages",
        "Evidence",
        "Fraud",
        "Jurisdiction",
        "Murder",
        "Negligence",
        "Sentence",
        "Sentencing",
        "Theft",
        "Trespass",
    }
    REFERENCE_TAIL_PATTERN = re.compile(
        r"^(?:"
        r"[A-Z][A-Za-z'()]+(?:\s+[A-Z][A-Za-z'()]+){0,8}\s+"
        r"(?:Act|Ordinance|Rules?|Code|Regulations?|Agreement)\b"
        r"(?:,?\s+\d{4})?"
        r"|[A-Z][A-Za-z'()]+(?:\s+[A-Z][A-Za-z'()]+){0,8}\s+Order in Council"
        r"|(?:Section|Sections|Order|Rule|Rules|Cap\.)\s*[\dIVXLCM]"
        r"|s\.\s*\d"
        r"|O\.\s*\d"
        r"|r\.\s*\d"
        r")",
        re.IGNORECASE,
    )
    BAD_TOP_LEVEL_ROOT_PATTERN = re.compile(
        r"^(?:"
        r"No\.?\s*\d+(?:/\d+)?(?:\s+of\s+\d{4})?"
        r"|Nos\.?\s*\d+"
        r"|(?:Section|Sections|Regulation|Regulations|Order|Orders|Rule|Rules|"
        r"Cap\.|Article|Articles|Schedule|Schedules|Item|Items|Part)\s+"
        r"[\dIVXLCM][\dIVXLCM()./-]*"
        r"|(?:s|ss|r|rr|o|ord)\.\s*\d"
        r"|[A-Z][A-Za-z'()/&.,]+(?:\s+[A-Z][A-Za-z'()/&.,]+){0,10}\s+"
        r"(?:Act|Ordinance|Rules?|Code|Regulations?|Order)\s*(?:,?\s*\d{4})?"
        r"(?:\s+(?:s|ss|r|rr|reg|rule|rules|item|part)\.?\s*"
        r"[\dIVXLCM()./-]+)?"
        r"|.*\b(?:Act|Acts?|Ordinance|Order|Rules?|Code)\b.*\bNo\.?\s*\d+.*"
        r")$",
        re.IGNORECASE,
    )
    BROAD_TOP_LEVEL_ROOT_PATTERN = re.compile(
        r"^(?:"
        r"[A-Z][A-Za-z/&'()]+(?:\s+[A-Za-z][A-Za-z/&'()]+){0,6}\s+"
        r"(?:law|procedure|practice)"
        r"|Court of Appeal Rules"
        r"|Judicial Notice"
        r")$",
        re.IGNORECASE,
    )
    NARROW_TOP_LEVEL_ROOT_PATTERN = re.compile(
        r"^(?:"
        r".*\b(?:appeal|appeals|appellate|evidence|injunction|injunctions|"
        r"jurisdiction|filing|dispute|disputes|damages|trespass|sentencing|"
        r"compensation|wills?|adoption|property|revisionary|electronic)\b.*"
        r")$",
        re.IGNORECASE,
    )
    INSTITUTIONAL_TOP_LEVEL_ROOT_PATTERN = re.compile(
        r"^(?:"
        r".*\b(?:court|courts|tribunal|division)\b.*"
        r"|Commercial Division"
        r"|Ward Tribunal(?:\s+composition)?"
        r"|Housing Tribunal"
        r"|Disputes Courts"
        r")$",
        re.IGNORECASE,
    )
    PROCEDURAL_FRAGMENT_ROOT_PATTERN = re.compile(
        r"^(?:"
        r".*\b(?:cause of action|proof|pleading|service|representation|"
        r"technical delay|computation of time|functus officio|interim injunction|"
        r"interim injunctions|electronic evidence|medical negligence|custody|"
        r"land acquisition|pecuniary jurisdiction|civil contempt|affidavit practice|"
        r"probate(?:/| & )administration|probate and administration|"
        r"execution(?:/attachment)?|summary procedure|case management|"
        r"criminal revision|land revision|bail pending (?:trial|appeal)|"
        r"special damages|objection proceedings|witness credibility|"
        r"proof beyond reasonable doubt|interlocutory injunction|"
        r"temporary injunctions?|recusal|disciplinary procedure|"
        r"execution procedure|professional conduct|contract evidence|"
        r"civil/criminal procedure|interpleader procedure|procedural economy|"
        r"appellate procedure|procedural appellate review|appellate threshold|"
        r"incorrect procedure|eviction proceedings|termination procedures?|"
        r"labour review|labour practice|labour practices|"
        r"computation of terminal benefits|employment practices|"
        r"representative procedure|contract expiry v\. termination|"
        r"administrative responsibility|administrative jurisdiction|"
        r"urgent applications?|closing submissions|evidentiary value|"
        r"procedural provision|post-judgment procedure|fresh evidence|"
        r"incompetence of proceedings|charge validity|time-frame)\b.*"
        r")$",
        re.IGNORECASE,
    )
    DANGLING_FRAGMENT_ROOT_PATTERN = re.compile(
        r"^(?:"
        r".*(?:&|/|,|:)\s*$"
        r"|.*\)\s*$"
        r"|.*\b(?:and|or|of|under|vs?|v)\s*$"
        r"|(?:Ct\.|Court|Republic)\s+of\s*$"
        r"|.*\(\s*$"
        r"|.*\b(?:Act|Rules?|Code|Order|Guidelines?)\)\s*$"
        r"|.*\bRules?\s+\d[\dA-Za-z(). &,-]*\band\s*$"
        r")$",
        re.IGNORECASE,
    )
    PROSE_LIKE_ROOT_PATTERN = re.compile(
        r"^(?:"
        r".*\b(?:must|should|may|cannot|not|fatal|quashed|set aside|"
        r"renders?|rendering|liable|satisfied|requires?|required|"
        r"available only|incompetent|invalid|unlawful|improper|"
        r"precluded|extinguish|sufficed?|sufficient|dismissed|shown|"
        r"is|are|was|were|err(?:ed)?|constitute(?:s|d)?|undermines?|"
        r"overtaken|acceptable explanations?|liable to be struck out|"
        r"application incomplete|application defective)\b.*"
        r")$",
        re.IGNORECASE,
    )
    QUOTED_DOCTRINE_ROOT_PATTERN = re.compile(
        r"^(?:"
        r"[\"'‘“].*"
        r"|.*\b(?:defined as|defined by|denotes|includes|depends on|doctrine|test)\b.*"
        r")$",
        re.IGNORECASE,
    )
    NUMERIC_RULE_ROOT_PATTERN = re.compile(
        r"^(?:"
        r"\d+(?:st|nd|rd|th|[-‑–]\w+)?\s+.*"
        r"|[0-9]{1,3}[-‑–](?:day|year|month).*$"
        r"|.*\b(?:day|days|year|years|percent|%)\b.*(?:requirement|rule|limit|period).*$"
        r"|.*\bSchedule\b.*(?:applies?|applicable).*$"
        r"|.*\bkg\b.*"
        r"|[.,]?\s*\d{4},\s*Order\s+\d+.*"
        r"|[A-Z]{2,}\s*s\.?\s*\d.*"
        r"|[A-Z]{2,}\s*r\.?\s*\d.*"
        r"|[A-Z]{1,6}\s+\d+(?:\([^)]+\))?.*"
        r"|[IVXLCM]+\s+r\.?\s*\d.*"
        r"|No\.?\s*\d+.*\b(?:para\.?|paragraph|item)\b.*"
        r"|.*\b(?:s\.|ss\.|r\.|rr\.|para\.?)\s*\d.*"
        r"|[A-Z][A-Za-z]{1,6}\.?\s+\d{4},\s*s\.?\s*\d.*"
        r"|[A-Z]{2,6}\s+s\.?\s*\d.*"
        r")$",
        re.IGNORECASE,
    )
    ROOT_LEADING_JUNK_PATTERN = re.compile(r"^[\s\[\]({\"'`“”‘’*•·^,;:!?\-–—]+")
    ROOT_TRAILING_JUNK_PATTERN = re.compile(r"[\s\[\]({\"'`“”‘’*•·^,.;:!?\-–—]+$")
    ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-9;:]*[A-Za-z]")
    ORPHAN_ANSI_FRAGMENT_PATTERN = re.compile(r"\[[0-9;:]+[A-Za-z]")
    CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x1f\x7f-\x9f]+")
    LEADING_ENUMERATION_PATTERN = re.compile(
        r"^(?:(?:[(]?\d+[)]?|[(]?[A-Za-z][)]?|[(]?[IVXLCMivxlcm]+[)]?)[.)\]]\s*)+"
    )
    UNMATCHED_OPEN_PAREN_SUFFIX_PATTERN = re.compile(r"\s*\([^)]*$")
    TRAILING_PARTIAL_CITATION_PAREN_PATTERN = re.compile(
        r"\s*\(.*\b(?:act|code|ordinance|rules?|regulations?|section|sections|s\.|ss\.|cap\.?)\b.*$",
        re.IGNORECASE,
    )
    TRAILING_CITATION_PAREN_PATTERN = re.compile(
        r"\s*\((?:s|ss|section|sections|order|rule|rules|reg(?:ulation)?s?|cap\.?|para\.?|item|items)\b[^)]*\)$",
        re.IGNORECASE,
    )
    TRAILING_CITATION_SUFFIX_PATTERN = re.compile(
        r"(?:,?\s+)(?:s\.|ss\.|section|sections|order|rule|rules|reg(?:ulation)?s?|"
        r"cap\.?|para\.?|item|items)\b\.?\s*[\w()./-]+$",
        re.IGNORECASE,
    )
    TINY_FRAGMENT_PATTERN = re.compile(
        r"^(?:[A-Z]{1,3}|[IVXLCM]{1,5}|G\.n\.|Ltd|Law|No|The)$",
        re.IGNORECASE,
    )
    OCR_FRAGMENT_PATTERN = re.compile(
        r"^(?:"
        r".*\b(?:j\ surisdiction|j urisdiction|piocedure|suspension of a)\b.*"
        r"|[A-Z][a-z]{0,2}$"
        r")$",
        re.IGNORECASE,
    )
    AUTHORITY_ROOT_PATTERN = re.compile(
        r"^(?:"
        r"(?:authorities?|cases?)\s*:\s*.*"
        r"|(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\s+v\.?\s+(?:[A-Z][A-Za-z'.-]+.*)"
        r"|(?:bushiri|pandya|mbowe|valambhia|lyamuya|farijala|sendi wambura|rajab simba|"
        r"fortuna(?:tus)?\s+masha|mehboob|park[ -]ross|rubambey|ladak|faulkner)\b.*"
        r"|(?:authorit(?:y|ies)|precedent)\s*:\s*.*"
        r")$",
        re.IGNORECASE,
    )
    PROPOSITION_START_PATTERN = re.compile(
        r"^(?:"
        r"failure to|mere |burden |validity of|interpretation of|"
        r"interpretation and application of|requirement of|requirement for|"
        r"necessity of|sufficiency of|effect of|meaning of|definition of|"
        r"absence of|presence of|burden on|need to|duty to|right to|"
        r"standard for|grounds for|remedy for|challenge to|distinction between|"
        r"promptness and|timeliness of|relevance of|credibility of|"
        r"appellant failed to|accused need only|accused under no duty|"
        r"any reasonable doubt|where reasonable doubt|unresolved doubts|"
        r"minimum quorum|no strict|no provision for|no need to|"
        r"whether |when |where |if "
        r")",
        re.IGNORECASE,
    )
    GENERIC_CIVIL_ROOT_PATTERN = re.compile(
        r"^(?:"
        r"procedure|civil procedure|civil practice and procedure|criminal procedure|"
        r"appeal|appeals|appellate procedure|appellate review|review|revision|"
        r"jurisdiction|remedy|remedies|limitation|limitation of actions|"
        r"pleadings?|costs?|execution|service|filing|interpleader|practice|"
        r"procedural .*|evidentiary .*|fresh evidence|evidence and procedure"
        r")$",
        re.IGNORECASE,
    )
    GENERIC_NON_LEAF_TOPIC_PATTERN = re.compile(
        r"^(?:"
        r"criminal|civil|offence|offences|procedural|procedure|practice|property|"
        r"remedy|remedies|doctrine|proof|requirement|requirements|standard|standards|"
        r"scope|role|evaluation|meaning|definition|effect|validity|application|"
        r"nature|element|elements|chain|question|test|unlawful|admissibility/weight|"
        r"unsafe|alternative|confirmed|confirmed|convict|convictions?|"
        r"substantive|proceedural|right|silence|service|treatment|seizure|"
        r"recording|existence|variation|review under|revision under|statement|"
        r"retraction|record|read|presence|complaint|cause|purpose|proper|"
        r"confirmed|certificate|conditions|complaint|question|issue|nature|"
        r"interpretation|weight|admission|acceptance|consideration"
        r")$",
        re.IGNORECASE,
    )
    NON_LEAF_DANGLING_FRAGMENT_PATTERN = re.compile(
        r".*\b(?:and|or|of|to|with|by|under|for|in|on|at|from|into|onto|against|between|versus|vs?\.?)$",
        re.IGNORECASE,
    )
    NON_LEAF_REFERENCE_ONLY_PATTERN = re.compile(
        r"^(?:"
        r"(?:s|ss|section|sections)\.?\s*\d[\w()./&, -]*"
        r"|(?:s|ss|section|sections)\.?\s*\d[\w()./&, -]*\b(?:act|code|ordinance|rules?)\b"
        r"|(?:article|articles)\s+\d[\w()./&, -]*"
        r"|(?:criminal procedure|evidence)\s+act\s+(?:s|ss)\.?\s*\d[\w()./&, -]*"
        r"|(?:criminal procedure code|penal code)\s+(?:s|ss)\.?\s*\d[\w()./&, -]*"
        r"|(?:no|rule|rules|order|orders)\.?\s*\d[\w()./&, -]*"
        r"|(?:tzs|kshs|usd)\.?\s*[\d,./=-]+\s*.*"
        r"|(?:section|sections)\s+[\d(][\w()./&, -]*"
        r"|(?:rule|rules)\s+[\d(][\w()./&, -]*"
        r"|cpa|eocca|pcca"
        r")$",
        re.IGNORECASE,
    )
    NON_LEAF_QUOTED_PROPOSITION_PATTERN = re.compile(
        r"^(?:"
        r".*(?:``.*''|[\"“”].*[\"“”]|‘.*’).*"
        r"|.*(?:^|\s)['‘][^'’]+['’](?:\s|$).*"
        r"|.*_[A-Za-z].*"
        r"|.*\bnot a defence\b.*"
        r")$",
        re.IGNORECASE,
    )
    NON_LEAF_SENTENCE_PROPOSITION_PATTERN = re.compile(
        r"^(?:"
        r"absence\b.*"
        r"|a\s+(?:court|district magistrate)\b.*"
        r"|absence\s+from\b.*"
        r"|the\s+defence\b.*"
        r"|the\s+graver\s+offence\s+prevails\b.*"
        r"|test\s+is\s+whether\b.*"
        r"|property\s+positively\b.*"
        r"|.*\bmust\b.*"
        r"|need\s+for\b.*"
        r"|necessity\b.*"
        r"|importance\b.*"
        r"|effect\s+of\b.*"
        r"|failure\s+to\b.*"
        r"|requirement\s+to\b.*"
        r"|requirements?\s+for\b.*"
        r")$",
        re.IGNORECASE,
    )
    NON_LEAF_LEADING_NUMERIC_PATTERN = re.compile(r"^[([]?\d")
    NON_LEAF_BARE_STATUTE_TOPIC_PATTERN = re.compile(
        r"^(?:"
        r"(?:evidence|criminal procedure|penal|wildlife conservation|road traffic)\s+act.*"
        r"|(?:criminal procedure|penal)\s+code.*"
        r"|eocca\b.*"
        r"|aja\b.*"
        r")$",
        re.IGNORECASE,
    )
    NON_LEAF_STATUTE_TITLE_PATTERN = re.compile(
        r"^(?:"
        r"(?:the\s+)?[a-z][a-z'’().,&/ -]*\b(?:act|ordinance|regulations?|by-laws|rules)\b"
        r"(?:\s*\d{4}|\s*(?:no\.?|cap\.?|s\.|ss\.|section|sections|rule|rules)\b.*)?"
        r"|(?:the\s+)?[a-z][a-z'’().,&/ -]*\bmunicipality\b.*\bby-laws\b.*"
        r")$",
        re.IGNORECASE,
    )
    NON_LEAF_SECTION_HEADING_PATTERN = re.compile(
        r"^(?:"
        r"(?:s|ss|section|sections)\.?\s*[\d(][\w()./&, -]*"
        r"|rule\s+\d[\w()./&, -]*"
        r"|order\s+\d[\w()./&, -]*"
        r")$",
        re.IGNORECASE,
    )
    HEAD_TOPIC_TRIGGER_PATTERN = re.compile(
        r"^(?:"
        r"(?:v|vs?\.?)\s+"
        r"|under(?:\s+(?:section|sections|s\.|ss\.|\d))?\b"
        r"|\([^)]*$"
        r"|requires?\b"
        r"|upheld\b"
        r"|by\s+night\b"
        r"|at\s+night\b"
        r"|and\s+(?:armed robbery|theft|violence)\b"
        r"|of\s+(?:girl|a girl)\b"
        r")",
        re.IGNORECASE,
    )
    ONE_WORD_SEPARATOR_HEAD_PATTERN = re.compile(
        r"^(?P<head>[A-Za-z][A-Za-z'’-]+)\s*(?:/|,\s+)\s*(?P<tail>.+)$"
    )
    HEAD_TOPIC_STOPWORDS = {
        "a",
        "an",
        "the",
        "of",
        "and",
        "or",
        "under",
        "with",
        "without",
        "by",
        "for",
        "to",
        "in",
        "on",
        "at",
        "against",
        "between",
        "v",
        "v.",
        "vs",
        "vs.",
    }
    STATUTE_TOPIC_ALIASES = {
        "admissibility of caution": "Admissibility of cautioned confession",
        "admissibility of cautioned": "Admissibility of cautioned confession",
        "admissibility of cautioned/confession": "Admissibility of cautioned confession",
        "admissibility of cautioned/confessional": "Admissibility of cautioned confession",
        "admissibility of confessions": "Confession",
        "admissibility/procedure": "Admissibility",
        "admissibility issues": "Admissibility",
        "admissibility of": "Admissibility",
        "cautioned": "Cautioned confession",
        "cautioned/confession": "Cautioned confession",
        "cautioned/confessional": "Cautioned confession",
        "cautions/confessions": "Cautioned confession",
        "cpa": "Criminal procedure",
        "criminal": "Criminal law",
        "criminal appeal": "Appeal",
        "criminal appeals": "Appeal",
        "criminal evidence": "Evidence",
        "criminal practice": "Criminal procedure",
        "criminal procedure code": "Criminal procedure",
        "criminal procedure act": "Criminal procedure",
        "criminal trespass s.299(1)(a) penal code": "Criminal trespass",
        "criminal trespass (s.299(a) penal code": "Criminal trespass",
        "criminal trespass (section 299(a) penal code": "Criminal trespass",
        "drug control act": "Drug offences",
        "arson/offences relating to setting fire": "Arson",
        "arson/destruction": "Arson",
        "arson/attempted arson": "Arson",
        "arson causing death": "Arson",
        "arson, burglary": "Arson",
        "arson (s. 519(a) penal code": "Arson",
        "entry into dwelling": "Search and seizure",
        "evidence act": "Evidence",
        "evidence act s.127(2) after 2016 amendment": "Evidence",
        "evidence act ss.127(5), 142, 143": "Evidence",
        "eyewitness evidence": "Identification evidence",
        "eyewitness identification at night": "Visual identification",
        "extra‑judicial": "Extra-judicial confession",
        "extra-judicial": "Extra-judicial confession",
        "extra‑judicial/confessional": "Extra-judicial confession",
        "extra-judicial/confessional": "Extra-judicial confession",
        "extra‑judicial/confessional statements to lay persons": "Extra-judicial confession",
        "extra-judicial/confessional statements to lay persons": "Extra-judicial confession",
        "extra‑judicial/confessional statements to lay persons": "Extra-judicial confession",
        "extrajudicial": "Extra-judicial confession",
        "fair hearing": "Fair trial",
        "fair trial rights": "Fair trial",
        "fair-trial rights": "Fair trial",
        "fair trial": "Fair trial",
        "failure to call material witness": "Failure to call material witnesses",
        "drugs": "Drug offences",
        "drug offences": "Drug offences",
        "drugs act": "Drug offences",
        "drugs control": "Drug offences",
        "drugs control and enforcement act": "Drug offences",
        "druug offences": "Drug offences",
        "eocca": "Economic offences",
        "eocca jurisdiction": "Economic offences",
        "evidence act s.143 single witness conviction": "Evidence",
        "extra‑judicial confession": "Extra-judicial confession",
        "extra-judicial confession": "Extra-judicial confession",
        "extra judicial confession": "Extra-judicial confession",
        "fair-trial rights": "Fair trial",
        "failure to call key witness": "Failure to call material witnesses",
        "failure to call witnesses": "Failure to call material witnesses",
        "failure to call crucial witness": "Failure to call material witnesses",
        "failure to call available witness": "Failure to call material witnesses",
        "failure to call available witnesses": "Failure to call material witnesses",
        "identification parade collateral": "Identification parade",
        "identification parades": "Identification parade",
        "identification procedures": "Identification",
        "identification evidence in darkness": "Visual identification",
        "identification evidence in night-time offences": "Visual identification",
        "identification evidence in armed robbery": "Identification evidence",
        "identification and recognition": "Visual identification",
        "house‑breaking": "Housebreaking",
        "housebreaking (s.294(1) penal code": "Housebreaking",
        "homicide/manslaughter": "Manslaughter",
        "medical (pf3) evidence": "Medical evidence",
        "medical report": "Medical evidence",
        "medical report (pf3)": "Medical evidence",
        "medical/forensic proof": "Medical evidence",
        "magistrates courts act": "Magistrates' courts",
        "magistrates courts act s.20(3)": "Magistrates' courts",
        "magistrates courts act s.20(3),(4": "Magistrates' courts",
        "magistrates' court act": "Magistrates' courts",
        "magistrates court act": "Magistrates' courts",
        "magistrates’ courts act": "Magistrates' courts",
        "magistrates' courts act s44": "Magistrates' courts",
        "magistrates' courts act s44(1)(b)": "Magistrates' courts",
        "magistrates' courts act s44(1)(b) and civil procedure code": "Magistrates' courts",
        "the defence (sale": "",
        "the defence (control": "",
        "minimum sentences act": "Sentencing",
        "incest (s.158(1)(a) penal code": "Incest",
        "penal code": "Criminal law",
        "pf3/medical report": "Medical evidence",
        "pf3 medical report": "Medical evidence",
        "pf.3": "Medical evidence",
        "pf3": "Medical evidence",
        "police procedure": "Police procedure",
        "police powers": "Police procedure",
        "police duties": "Police procedure",
        "police duty to investigate and charge appropriately": "Police procedure",
        "police use of force in effecting arrest or preventing escape": "Police procedure",
        "police participation may taint its value": "Police procedure",
        "police general orders on exhibit handovers": "Police procedure",
        "police general orders and section 39 anti‑drugs act compliance": "Police procedure",
        "police form no.91": "Police procedure",
        "police acting": "Police procedure",
        "police sting (marked notes) as evidence": "Police procedure",
        "police identification": "Identification",
        "police-station identifications versus in-court identification": "Identification",
        "pcca": "Corruption",
        "prevention of corruption act": "Corruption",
        "receiving/possession": "Receiving stolen property",
        "receiving stolen property (s.311(1) penal code": "Receiving stolen property",
        "recognition vs identification": "Visual identification",
        "res ipsa loquitur": "",
        "right to fair hearing": "Fair trial",
        "right to fair trial": "Fair trial",
        "right to interpreter": "Fair trial",
        "right to interpretation": "Fair trial",
        "right to be defended": "Fair trial",
        "right to be heard and to cross-examine": "Fair trial",
        "right to cross-examination": "Fair trial",
        "right to cross-examine": "Fair trial",
        "right to cross-examine witnesses": "Fair trial",
        "right to full hearing": "Fair trial",
        "right to a fair hearing": "Fair trial",
        "right to legal representation": "Fair trial",
        "robbery/armed": "Armed robbery",
        "robbery/armed robbery": "Armed robbery",
        "road traffic act": "Road traffic",
        "revision application": "Revision",
        "revisional jurisdiction": "Revision",
        "revisional powers": "Revision",
        "revision under": "Revision",
        "revision powers": "Revision",
        "revisional power": "Revision",
        "revisional powers": "Revision",
        "revisional powers under": "Revision",
        "revisional jurisdiction (s.37(1) criminal procedure code": "Revision",
        "review under": "Review",
        "review district from appeal": "Review",
        "retrial as remedy": "Retrial",
        "retrial de novo": "Retrial",
        "searches": "Search and seizure",
        "search permits": "Search and seizure",
        "search without warrant": "Search and seizure",
        "search and seizure lawfulness": "Search and seizure",
        "search procedure": "Search and seizure",
        "seizure certificate": "Search and seizure",
        "seizure procedure": "Search and seizure",
        "seizure certificate": "Search and seizure",
        "seizure certificate vs receipt (s.38(3) cpa": "Search and seizure",
        "sexual offence": "Sexual offences",
        "sexual offenses": "Sexual offences",
        "sexual offence trials": "Sexual offences",
        "sexual offences against children": "Sexual offences involving children",
        "sexual offences involving a child": "Sexual offences involving children",
        "sexual offences involving children": "Sexual offences involving children",
        "child sexual offence": "Sexual offences involving children",
        "child sexual offences": "Sexual offences involving children",
        "statutory construction": "Statutory interpretation",
        "store‑breaking": "Storebreaking",
        "store breaking": "Storebreaking",
        "store breaking/housebreaking": "Housebreaking",
        "storebreaking/theft": "Storebreaking",
        "attempted rape (s.132(1)": "Attempted rape",
        "trial in absentia after accused absconds": "Trial in absentia",
        "trial-within-trial procedure": "Trial-within-trial",
        "trial proceedings": "Trial procedure",
        "unsafe convictions": "Unsafe conviction",
        "unlawful possession": "Possession offences",
        "unlawful possession of firearm": "Possession offences",
        "unsworn statement": "Unsworn evidence",
        "visual/dock identification": "Visual identification",
        "visual identification/recognition": "Visual identification",
        "wildlife conservation act": "Wildlife offences",
        "wildlife conservation": "Wildlife offences",
        "wildlife law": "Wildlife offences",
        "wildlife trophies": "Wildlife offences",
    }
    GENERIC_CRIMINAL_ROOT_PATTERN = re.compile(
        r"^(?:"
        r"criminal law|criminal procedure|sentencing|sentence|bail|conviction|"
        r"charge validity|proof beyond reasonable doubt|hearsay and admissions|"
        r"evidence|evidentiary value(?: of .*)?|drug offences|wildlife offence"
        r")$",
        re.IGNORECASE,
    )
    GENERIC_LAND_ROOT_PATTERN = re.compile(
        r"^(?:"
        r"land law|land procedure|land dispute|property(?: & land law)?|"
        r"mortgage(?:e remedies| security)?|lease|rent|sale of land|"
        r"contract of sale of land|eviction proceedings|title|trespass"
        r")$",
        re.IGNORECASE,
    )
    GENERIC_LABOUR_ROOT_PATTERN = re.compile(
        r"^(?:labour .*|employment .*|collective bargaining|termination .*|employer policy)$",
        re.IGNORECASE,
    )
    GENERIC_FAMILY_ROOT_PATTERN = re.compile(
        r"^(?:family .*|marriage .*|divorce.*|maintenance.*|child .*|custody)$",
        re.IGNORECASE,
    )
    GENERIC_PROBATE_ROOT_PATTERN = re.compile(
        r"^(?:probate .*|succession|wills?|estate .*|administration of estates?)$",
        re.IGNORECASE,
    )
    GENERIC_CONTRACT_ROOT_PATTERN = re.compile(
        r"^(?:contract .*|commercial .*|company law|shareholder .*|bank .*|banking .*|sale of goods)$",
        re.IGNORECASE,
    )
    CIVIL_REFERENCE_ROOT_PATTERN = re.compile(
        r"^(?:"
        r".*\b(?:civil procedure code|cpc|order|orders|rule|rules)\b.*"
        r"|.*\bcivil procedure\b.*"
        r"|.*\b(?:leave to appeal|appeal leave|computation of appeal period|default notice|filing fees?)\b.*"
        r")$",
        re.IGNORECASE,
    )
    CRIMINAL_REFERENCE_ROOT_PATTERN = re.compile(
        r"^(?:"
        r".*\b(?:cpa|criminal procedure code|eocca)\b.*"
        r"|.*\bcriminal procedure\b.*"
        r"|.*\b(?:dpp consent|criminal trespass|charge-sheet defects|curability under s\.|"
        r"voluntariness requirement|cautioned statements?)\b.*"
        r")$",
        re.IGNORECASE,
    )
    ADMINISTRATIVE_REFERENCE_ROOT_PATTERN = re.compile(
        r"^(?:.*\b(?:administrative|parastatal|union law|judicial review only)\b.*)$",
        re.IGNORECASE,
    )
    LAND_REFERENCE_ROOT_PATTERN = re.compile(
        r"^(?:.*\b(?:land practice and procedure|transfer of title|housing|"
        r"security interests|urban planning|compulsory acquisition)\b.*)$",
        re.IGNORECASE,
    )
    PROBATE_REFERENCE_ROOT_PATTERN = re.compile(
        r"^(?:.*\b(?:assessors['’] role|assessors['’] procedure|"
        r"magistrates['’] procedure|succession and land law|wills? valid)\b.*)$",
        re.IGNORECASE,
    )
    CONTRACT_REFERENCE_ROOT_PATTERN = re.compile(
        r"^(?:.*\b(?:contractual compound interest|letter of credit|settlement agreements?)\b.*)$",
        re.IGNORECASE,
    )
    COMMERCIAL_REFERENCE_ROOT_PATTERN = re.compile(
        r"^(?:.*\b(?:insolvency|company|shareholder|business owner|debts?|assets?|debenture|commercial)\b.*)$",
        re.IGNORECASE,
    )
    SAFE_CLASSIFIED_TOP_LEVELS = {
        "Administrative law",
        "Appellate practice",
        "Arbitration",
        "Banking law",
        "Civil procedure",
        "Commercial law",
        "Company law",
        "Competition law",
        "Constitutional law",
        "Construction law",
        "Consumer protection",
        "Contract law",
        "Criminal law",
        "Criminal procedure",
        "Customary law",
        "Customs law",
        "Defamation",
        "Education law",
        "Employment law",
        "Election law",
        "Environmental law",
        "Evidence",
        "Family law",
        "Health law",
        "Human rights",
        "Immigration law",
        "Insurance law",
        "Intellectual property law",
        "International law",
        "Conflict of laws",
        "Islamic law",
        "Judicial review",
        "Labour law",
        "Land disputes",
        "Land law",
        "Legal profession",
        "Limitation law",
        "Maritime law",
        "Media law",
        "Military law",
        "Mining law",
        "Prison law",
        "Probate law",
        "Procurement law",
        "Regional integration law",
        "Road traffic law",
        "Sports law",
        "Succession law",
        "Tax law",
        "Telecommunications law",
        "Tort",
        "Trust law",
        "Water law",
        "Wildlife law",
    }
    GENERIC_NON_ROOT_PATTERN = re.compile(
        r"^(?:"
        r"national|public|local|regional|international|east|high|small|ward|district|primary|"
        r"human|legal|civil law|substantive law|procedural law|private law|public law|"
        r"law of the|leave to|result|outcome|effect|requirement|requirements|conditions|"
        r"consequences|timing|general|records?|proceedings|issues|facts|documents|"
        r"applicable law|relevant law|rights law|standard|minimum|process|scope|"
        r"factors|considerations|grounds|access|conduct|duty|duties|powers|rights|"
        r"relief granted|relief refused|alternative|suitability|subject matter|subject-matter"
        r")$",
        re.IGNORECASE,
    )
    LONG_CHAIN_PART_THRESHOLD = 8
    LONG_CHAIN_ANCHOR_WORD_LIMIT = 12
    ISSUE_FRAGMENT_PATTERN = re.compile(
        r"^(?:"
        r"whether\b|when\b|where\b|if\b|or\b|no\b|effect of\b|status of\b|"
        r"manner in which\b|power of\b|"
        r"procedural\b|use and function\b|what\b|why\b|how\b|"
        r".*\b(?:right|duty|power|effect|status|manner|error|justice)\b.*"
        r")",
        re.IGNORECASE,
    )
    PRESERVE_LITERAL_ROOTS = {
        "administrative law",
        "civil practice and procedure",
        "contract",
        "damages",
        "judicial notice",
        "jurisdiction",
        "land law",
        "natural justice",
        "trespass",
    }
    FORCE_NEW_ROOTS = {
        "termination of employment",
    }

    @staticmethod
    def clean(text):
        """Normalise whitespace in a flynote.

        Preserves line breaks so multi-line flynotes can be interpreted as one
        flynote per line. Within each line, whitespace is normalised, leading
        bullet characters are removed, and trailing periods are stripped.
        """
        if not text:
            return ""

        text = unescape(text)
        text = FlynoteParser.ANSI_ESCAPE_PATTERN.sub("", text)
        text = FlynoteParser.ORPHAN_ANSI_FRAGMENT_PATTERN.sub("", text)
        text = text.replace("&nbsp;", " ")
        text = text.replace("\xa0", " ")

        lines = []
        for line in text.strip().splitlines():
            line = FlynoteParser.CONTROL_CHAR_PATTERN.sub("", line)
            line = re.sub(r"\s+", " ", line)
            line = re.sub(
                r"^[\-\u2010\u2011\u2012\u2013\u2014\u2022\u2023\u25E6\u2043\s]+",
                "",
                line,
            )
            line = re.sub(r"^[\*\u00b7]+\s*", "", line)
            line = re.sub(r"^(?:&[A-Za-z]+;?)+\s*", "", line)
            line = line.strip().rstrip(".")
            if line:
                lines.append(line)
        return "\n".join(lines)

    def normalise_multiline_text(self, text):
        """Normalise flynote text into one flynote per line."""
        text = self.clean(text)
        if not text:
            return ""

        text = self._strip_held_section(text)
        candidates = []
        for line in text.splitlines():
            candidates.extend(self._split_line_into_candidates(line))

        return "\n".join(self._dedupe_candidates(candidates))

    def parse(self, text):
        """Parse flynote text into a list of paths.

        The parsing works as follows:

        1. Whitespace is normalised and trailing periods are removed
           (via ``clean``).
        2. If no dash characters (em-dash, en-dash, or spaced hyphen) are
           found, the text is treated as plain prose and an empty list is
           returned.
        3. The text is split into lines and each line is treated as a separate
           flynote.
        4. Within each flynote, the text is split on semicolons into segments.
        5. Each segment is split on dashes into parts, forming a hierarchy
           from general to specific.
        6. For the first segment in a flynote, the parts become the initial
           path.
        7. For each subsequent segment in that flynote, the number of
           dash-separated parts (n) determines how many levels from the bottom
           of the current path are replaced. This allows sibling or cousin
           branches to share a common prefix.

        Examples::

            >>> parser = FlynoteParser()

            # Single chain – three levels deep
            >>> parser.parse("Criminal law — admissibility — trial within a trial")
            [['Criminal law', 'admissibility', 'trial within a trial']]

            # Semicolons create sibling branches (1 part replaces the last level)
            >>> parser.parse(
            ...     "Criminal law — admissibility — trial within a trial; "
            ...     "right to representation"
            ... )
            [['Criminal law', 'admissibility', 'trial within a trial'],
             ['Criminal law', 'admissibility', 'right to representation']]

            # Two dash-separated parts replace the last two levels
            >>> parser.parse(
            ...     "Criminal law — admissibility — trial; "
            ...     "circumstantial evidence — Blom principles"
            ... )
            [['Criminal law', 'admissibility', 'trial'],
             ['Criminal law', 'circumstantial evidence', 'Blom principles']]

            # Plain prose (no dashes) returns an empty list
            >>> parser.parse("Contract between a lender and a borrower.")
            []

        Args:
            text: Raw flynote string.

        Returns:
            A list of paths, where each path is a list of strings from
            root to leaf.  Returns an empty list if the text is empty,
            has no dashes, or is plain prose.
        """
        text = self.clean(text)

        if not text:
            return []

        if not re.search(self.DASH_PATTERN, text):
            return []

        paths = []
        for line in self.normalise_multiline_text(text).splitlines():
            segments = [s.strip() for s in self._split_segments(line) if s.strip()]
            if len(segments) == 1:
                line_paths = self._parse_single_segment_line(segments[0])
                if line_paths:
                    paths.extend(line_paths)
                    continue
            current_path = []

            for segment in segments:
                parts = [
                    p.strip()[: self.MAX_NAME_LENGTH]
                    for p in self._split_dash_parts(segment)
                    if p.strip()
                ]
                parts = self._prepare_parts(parts, current_path)
                if not parts:
                    continue

                n = len(parts)
                if not current_path:
                    if self._looks_like_bad_top_level_root(parts[0]):
                        continue
                    current_path = parts
                else:
                    if self._should_start_new_root(current_path, parts):
                        replace_from = 0
                    elif n == 1:
                        replace_from = max(len(current_path) - 1, 1)
                    else:
                        replace_from = 1
                    current_path = self._dedupe_adjacent_parts(
                        current_path[:replace_from] + parts
                    )

                paths.append(list(current_path))

        return paths

    def _parse_single_segment_line(self, segment):
        parts = [
            p.strip()[: self.MAX_NAME_LENGTH]
            for p in self._split_dash_parts(segment)
            if p.strip()
        ]
        parts = self._prepare_parts(parts, current_path=[])
        if not parts:
            return []

        if self._looks_like_bad_top_level_root(parts[0]):
            return []

        expanded = self._expand_long_chain(parts)
        return [
            cleaned_path
            for path in expanded
            if path
            for cleaned_path in [self._dedupe_adjacent_parts(path)]
            if cleaned_path
        ]

    def _prepare_parts(self, parts, current_path):
        parts = self._trim_reference_tail(parts)
        if not parts:
            return []

        if not current_path or (
            len(parts) > 1 and self._looks_like_broad_top_level_root(parts[0])
        ):
            parts[0] = self.canonicalise_root_name(parts[0])
        if not parts[0]:
            return []

        wrapped_inserted_part = None
        if not current_path:
            original_parts = list(parts)
            parts = self._wrap_under_classified_top_level(parts)
            if not parts:
                return []
            if len(parts) > len(original_parts):
                wrapped_inserted_part = parts[1]
        elif len(parts) > 1 and parts[0] == current_path[0]:
            parts = parts[1:]
            if not parts:
                return []

        cleaned_parts = []
        had_non_root_parts = len(parts) > 1
        for index, part in enumerate(parts):
            preserve_reference_branch = (
                wrapped_inserted_part is not None
                and index == 1
                and part == wrapped_inserted_part
            ) or (
                current_path
                and index == 0
                and len(parts) > 1
                and (
                    self.NON_LEAF_REFERENCE_ONLY_PATTERN.match(part)
                    or self.NON_LEAF_STATUTE_TITLE_PATTERN.match(part)
                    or self.NON_LEAF_BARE_STATUTE_TOPIC_PATTERN.match(part)
                    or self.NON_LEAF_LEADING_NUMERIC_PATTERN.match(part)
                    or self.BAD_TOP_LEVEL_ROOT_PATTERN.match(part)
                    or "/" in part
                    or "(" in part
                    or part.endswith(")")
                    or part[:1] in ".,;"
                    or re.search(
                        r"\b(?:Act|Code|Rules?|Ordinance|By-laws),\s*(?:Cap\.?|No\.?)",
                        part,
                        re.IGNORECASE,
                    )
                    or re.match(r"^Order\s+\w+", part, re.IGNORECASE)
                )
            )
            cleaned = self.clean_path_part(
                part,
                is_root=index == 0 and not current_path,
                allow_alias=not current_path
                or part[:1].isupper()
                or part.casefold().startswith(("arson", "police")),
                allow_leading_numeric=index == 0 and len(parts) > 1,
                allow_generic_stub=index == 0 and len(parts) > 1,
                preserve_literal=preserve_reference_branch,
            )
            if cleaned:
                cleaned_parts.append(cleaned)

        if had_non_root_parts and len(cleaned_parts) == 1:
            return []

        if (
            not current_path
            and len(parts) == 2
            and len(cleaned_parts) == 2
            and (
                self.NON_LEAF_REFERENCE_ONLY_PATTERN.match(parts[1])
                or self.NON_LEAF_STATUTE_TITLE_PATTERN.match(parts[1])
                or self.NON_LEAF_BARE_STATUTE_TOPIC_PATTERN.match(parts[1])
            )
        ):
            return []

        return self._dedupe_adjacent_parts(cleaned_parts)

    @classmethod
    def _split_segments(cls, text):
        segments = []
        current = []
        depth = 0
        for idx, ch in enumerate(text):
            if ch == "(":
                depth += 1
                current.append(ch)
            elif ch == ")":
                depth = max(depth - 1, 0)
                current.append(ch)
            elif ch == ";" and depth == 0:
                segments.append("".join(current))
                current = []
            elif (
                ch == ";"
                and depth > 0
                and re.match(
                    r"\s*[A-Z][A-Za-z'’/&() -]{0,80}(?:\s*[\u2014\u2013]\s*|\s+[-\u2010\u2011\u2012]\s+)",
                    text[idx + 1 :],
                )
            ):
                segments.append("".join(current))
                current = []
                depth = 0
            else:
                current.append(ch)
        if current:
            segments.append("".join(current))
        return segments

    def _split_dash_parts(self, text):
        """Split a hierarchy segment on dashes, ignoring dashes inside parentheses."""
        parts = []
        current = []
        depth = 0
        i = 0

        while i < len(text):
            ch = text[i]
            if ch == "(":
                if ")" in text[i:]:
                    depth += 1
                current.append(ch)
                i += 1
                continue
            if ch == ")":
                depth = max(depth - 1, 0)
                current.append(ch)
                i += 1
                continue

            if depth == 0:
                match = re.match(self.DASH_PATTERN, text[i:])
                if match:
                    parts.append("".join(current))
                    current = []
                    i += match.end()
                    continue

            current.append(ch)
            i += 1

        if current:
            parts.append("".join(current))

        return parts

    @staticmethod
    def _should_start_new_root(current_path, parts):
        if not current_path or not parts:
            return False

        if len(parts) == 1:
            return False

        first_alpha = re.search(r"[A-Za-z]", parts[0])
        if not first_alpha:
            return False

        if parts[0][first_alpha.start()].islower():
            return False

        if current_path[0] == parts[0]:
            return False

        if FlynoteParser._looks_like_bad_top_level_root(parts[0]):
            return False

        inferred = FlynoteParser.infer_top_level_root(parts[0])
        if inferred and inferred == current_path[0] and "/" in parts[0]:
            return False
        if (
            inferred
            and inferred == current_path[0]
            and parts[0].casefold() in FlynoteParser.FORCE_NEW_ROOTS
        ):
            return True

        return FlynoteParser._looks_like_broad_top_level_root(parts[0])

    @classmethod
    def _looks_like_bad_top_level_root(cls, text):
        root = text.strip()
        if not root:
            return False

        if root.startswith("("):
            return True

        if root.count("(") != root.count(")"):
            return True

        if cls.TINY_FRAGMENT_PATTERN.match(root):
            return True

        if cls.OCR_FRAGMENT_PATTERN.match(root):
            return True

        if cls.BAD_TOP_LEVEL_ROOT_PATTERN.match(root):
            return True

        if cls.AUTHORITY_ROOT_PATTERN.match(root):
            return True

        if re.search(r"[).]\s*\bact\b.*\bno\.?\s*\d+", root, re.IGNORECASE):
            return True

        if re.search(
            r"\b(?:ord\.?|act|code|cpc|cpa|wca|ldca|pcca|eocca)\b.*\b(?:s\.|ss\.|r\.|rr\.|para\.?)\s*\d+",
            root,
            re.IGNORECASE,
        ):
            return True

        if re.search(r"\b(?:cap\.|r\.e\.|re\.)\s*\d*", root, re.IGNORECASE):
            return True

        if re.search(r"\bno\.?\s*\d+\s+of\s+\d{4}\b", root, re.IGNORECASE):
            return True

        if cls.INSTITUTIONAL_TOP_LEVEL_ROOT_PATTERN.match(root):
            return True

        if cls.PROCEDURAL_FRAGMENT_ROOT_PATTERN.match(root):
            return True

        if cls.DANGLING_FRAGMENT_ROOT_PATTERN.match(root):
            return True

        if root[:1].islower():
            return True

        if cls.PROSE_LIKE_ROOT_PATTERN.match(root):
            return True

        if cls.PROPOSITION_START_PATTERN.match(root):
            return True

        if cls.QUOTED_DOCTRINE_ROOT_PATTERN.match(root):
            return True

        if cls.NUMERIC_RULE_ROOT_PATTERN.match(root):
            return True

        if not re.search(r"[A-Za-z]", root):
            return True

        if re.search(r"[\u0600-\u06FF]", root):
            return True

        if root[:1] in ".,;":
            return True

        if "/" in root and (
            not cls._looks_like_broad_top_level_root(root)
            or not root.strip().lower().endswith("law")
        ):
            return True

        if (
            "(" in root
            and ")" in root
            and not cls._looks_like_broad_top_level_root(root)
        ):
            return True

        if re.search(
            r"\b(?:Act|Code|Ordinance|Rules?|Regulations?|Order|Orders)\b.*\b"
            r"(?:s\.|ss\.|section|sections|rule|rules|cap\.?|item|items)\b",
            root,
            re.IGNORECASE,
        ):
            return True

        if re.search(
            r"^(?:use of|under|pursuant to)\s+\b(?:section|sections|s\.|rule|rules|order|cap\.?|item)\b",
            root,
            re.IGNORECASE,
        ):
            return True

        if re.search(
            r"\b(?:article|articles|section|sections|cap\.?|r\.e\.|re\.)\b",
            root,
            re.IGNORECASE,
        ) and not cls._looks_like_broad_top_level_root(root):
            return True

        if re.search(
            r"\b(?:read with|item\s+\d+|part\s+[ivxlcm]+|schedule\s+\w+)\b",
            root,
            re.IGNORECASE,
        ):
            return True

        alpha_chars = sum(ch.isalpha() for ch in root)
        digit_chars = sum(ch.isdigit() for ch in root)
        if digit_chars and alpha_chars <= 2:
            return True

        if cls.GENERIC_NON_ROOT_PATTERN.match(root):
            return True

        return False

    @classmethod
    def _looks_like_broad_top_level_root(cls, text):
        root = text.strip()
        if not cls.BROAD_TOP_LEVEL_ROOT_PATTERN.match(root):
            return False

        if cls.NARROW_TOP_LEVEL_ROOT_PATTERN.match(root):
            return False

        return True

    def _strip_held_section(self, text):
        return self.HELD_PATTERN.split(text, maxsplit=1)[0].strip()

    def _split_line_into_candidates(self, line):
        if not line:
            return []

        parts = self.SENTENCE_BOUNDARY_PATTERN.split(line)
        candidates = []
        current = ""

        for part in parts:
            part = self._clean_candidate(part)
            if not part:
                continue

            if current and self._starts_new_flynote(part):
                candidates.append(current)
                current = part
            else:
                current = f"{current}. {part}" if current else part

        if current:
            candidates.append(current)

        split_candidates = []
        for candidate in candidates:
            split_candidates.extend(self._split_topic_restarts(candidate))

        return split_candidates

    def _starts_new_flynote(self, text):
        head = text[:120]
        if not re.search(self.DASH_PATTERN, head):
            return False

        parts = [p.strip() for p in self._split_dash_parts(text) if p.strip()]
        if len(parts) < 2:
            return False

        return self._looks_like_heading_phrase(parts[0], allow_single_word=True)

    def _clean_candidate(self, text):
        text = text.strip().rstrip(".;,")
        text = self.REPORT_MARKER_PATTERN.sub("", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _split_topic_restarts(self, text):
        boundaries = set()
        for match in self.TOPIC_RESTART_PATTERN.finditer(text):
            if match.start() == 0:
                continue

            boundary_kind = self._topic_restart_boundary_kind(text, match.start())
            if not boundary_kind:
                continue

            split_at = match.start()
            if boundary_kind == "embedded":
                split_at = self._embedded_topic_restart_index(text, match)
                if split_at is None:
                    continue

            if re.search(self.DASH_PATTERN + r"$", text[:split_at]):
                continue

            if not self._looks_like_topic_restart(
                text[split_at:],
                re.match(self.TOPIC_RESTART_PATTERN, text[split_at:]),
                allow_single_word=(boundary_kind == "embedded"),
            ):
                continue

            boundaries.add(split_at)

        for match in self.EMBEDDED_TITLE_RESTART_PATTERN.finditer(text):
            if match.start() == 0:
                continue

            if not self._topic_restart_boundary_kind(text, match.start()):
                continue

            if re.search(self.DASH_PATTERN + r"$", text[: match.start()]):
                continue

            if not self._looks_like_topic_restart(
                text[match.start() :],
                re.match(self.TOPIC_RESTART_PATTERN, text[match.start() :]),
                allow_single_word=False,
            ):
                continue

            boundaries.add(match.start())

        for match in self.EMBEDDED_SINGLE_TOPIC_PATTERN.finditer(text):
            if match.start() == 0:
                continue

            if not self._topic_restart_boundary_kind(text, match.start()):
                continue

            if match.group("phrase") not in self.EMBEDDED_SINGLE_TOPIC_WORDS:
                continue

            if re.search(self.DASH_PATTERN + r"$", text[: match.start()]):
                continue

            if not self._looks_like_topic_restart(
                text[match.start() :],
                re.match(self.TOPIC_RESTART_PATTERN, text[match.start() :]),
                allow_single_word=True,
            ):
                continue

            boundaries.add(match.start())

        if not boundaries:
            return [text]

        boundaries = sorted(boundaries)
        parts = []
        start = 0
        for boundary in boundaries:
            part = text[start:boundary].strip()
            if part:
                parts.append(part)
            start = boundary

        tail = text[start:].strip()
        if tail:
            parts.append(tail)

        return parts

    @staticmethod
    def _topic_restart_boundary_kind(text, index):
        prefix = text[:index].rstrip()
        if not prefix:
            return None

        if prefix[-1] in ".;:":
            return "punctuation"

        last_word_match = re.search(r"([A-Za-z0-9][A-Za-z0-9'’()]*)\s*$", prefix)
        if not last_word_match:
            return None

        last_word = last_word_match.group(1)
        if last_word.casefold() in {
            "the",
            "a",
            "an",
            "of",
            "and",
            "or",
            "to",
            "in",
            "for",
            "by",
            "under",
            "with",
            "is",
            "that",
            "this",
        }:
            return None

        if last_word[0].islower() or last_word[0].isnumeric():
            return "embedded"

        return None

    def _embedded_topic_restart_index(self, text, match):
        phrase = match.group("phrase").strip()
        words = phrase.split()
        if len(words) <= 4 and self._looks_like_heading_phrase(
            phrase, allow_single_word=True
        ):
            return match.start()

        for size in range(min(4, len(words)), 1, -1):
            suffix_words = words[-size:]
            suffix_phrase = " ".join(suffix_words)
            if not self._looks_like_heading_phrase(
                suffix_phrase, allow_single_word=False
            ):
                continue

            suffix_start = text.find(suffix_phrase, match.start(), match.end())
            if suffix_start != -1:
                return suffix_start

        return None

    def _looks_like_topic_restart(self, text, match, allow_single_word=False):
        if not match:
            return False

        phrase = match.group("phrase").strip()
        if not self._looks_like_heading_phrase(
            phrase, allow_single_word=allow_single_word
        ):
            return False

        tail = text[match.start() :].strip()
        if len([p for p in self._split_dash_parts(tail) if p.strip()]) < 2:
            return False

        return True

    @staticmethod
    def _looks_like_heading_phrase(phrase, allow_single_word):
        words = re.findall(r"[A-Za-z][A-Za-z/&'()]+", phrase)
        if not 1 <= len(words) <= 8:
            return False

        phrase_lc = phrase.casefold()
        if phrase_lc.startswith(
            (
                "whether ",
                "when ",
                "where ",
                "if ",
                "right to ",
                "duty to ",
                "failure to ",
                "requirement of ",
                "application for ",
                "submission on ",
                "scope of ",
                "independence of ",
                "recognition of ",
                "conclusion:",
            )
        ):
            return False

        connector_words = {
            "and",
            "of",
            "the",
            "in",
            "on",
            "for",
            "to",
            "at",
            "by",
            "under",
            "with",
            "or",
            "v",
        }

        has_title_word = False
        title_word_count = 0
        for index, word in enumerate(words):
            if word.islower():
                # Many legal headings are sentence case, e.g.
                # "Civil practice and procedure" or "Land law".
                if index == 0:
                    return False
                if word.casefold() not in connector_words:
                    continue
                continue

            if word.casefold() in connector_words:
                if index == 0:
                    return False
                continue

            if word[0].isupper():
                has_title_word = True
                title_word_count += 1
                continue

            return False

        if not has_title_word:
            return False

        if not allow_single_word and title_word_count < 2:
            return False

        return True

    def _trim_reference_tail(self, parts):
        trimmed = []
        for idx, part in enumerate(parts):
            if idx >= 2 and self._looks_like_reference_tail(part):
                break
            trimmed.append(part)
        return trimmed

    def _looks_like_reference_tail(self, part):
        text = part.strip()
        if not text:
            return False

        if not self.REFERENCE_TAIL_PATTERN.search(text):
            return False

        # Don't drop substantive issue statements that merely cite a section.
        if text.lower().startswith(
            (
                "whether ",
                "when ",
                "if ",
                "where ",
                "duty ",
                "right ",
                "application under ",
            )
        ):
            return False

        return True

    def _dedupe_candidates(self, candidates):
        seen = set()
        deduped = []

        for candidate in candidates:
            candidate = self._clean_candidate(candidate)
            if not candidate:
                continue

            canonical = self._canonicalise_candidate(candidate)
            if canonical in seen:
                continue

            seen.add(canonical)
            deduped.append(candidate)

        return deduped

    @staticmethod
    def _canonicalise_candidate(text):
        text = text.casefold()
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"\s*[\u2014\u2013-]\s*", " - ", text)
        return text.strip(" .;,")

    @staticmethod
    def normalise_name(name):
        """Convert a topic name to a slug for deduplication matching."""
        return slugify(name)

    @classmethod
    def _basic_normalise_topic_name(cls, text):
        text = unescape(text or "")
        text = cls.ANSI_ESCAPE_PATTERN.sub("", text)
        text = cls.ORPHAN_ANSI_FRAGMENT_PATTERN.sub("", text)
        text = cls.CONTROL_CHAR_PATTERN.sub("", text)
        text = re.sub(r"\s+", " ", text).strip()
        text = cls.LEADING_ENUMERATION_PATTERN.sub("", text).strip()
        text = cls.ROOT_LEADING_JUNK_PATTERN.sub("", text)
        text = cls.ROOT_TRAILING_JUNK_PATTERN.sub("", text)
        return text.strip()

    @classmethod
    def _basic_normalise_literal_topic_name(cls, text):
        text = unescape(text or "")
        text = cls.ANSI_ESCAPE_PATTERN.sub("", text)
        text = cls.ORPHAN_ANSI_FRAGMENT_PATTERN.sub("", text)
        text = cls.CONTROL_CHAR_PATTERN.sub("", text)
        return re.sub(r"\s+", " ", text).strip()

    @classmethod
    def _strip_citation_suffix(cls, text):
        text = cls.UNMATCHED_OPEN_PAREN_SUFFIX_PATTERN.sub("", text).strip()
        text = cls.TRAILING_PARTIAL_CITATION_PAREN_PATTERN.sub("", text).strip()
        text = cls.TRAILING_CITATION_PAREN_PATTERN.sub("", text).strip()
        previous = None
        while previous != text:
            previous = text
            text = cls.TRAILING_CITATION_SUFFIX_PATTERN.sub("", text).strip()
        return cls.ROOT_TRAILING_JUNK_PATTERN.sub("", text).strip()

    @classmethod
    def clean_path_part(
        cls,
        part,
        is_root=False,
        allow_alias=True,
        allow_leading_numeric=False,
        allow_generic_stub=False,
        preserve_literal=False,
    ):
        original_part = part
        if preserve_literal:
            return cls._basic_normalise_literal_topic_name(part)

        part = cls._basic_normalise_topic_name(part)
        if not part:
            return ""

        if part.casefold().startswith(
            (
                "application under ",
                "illegality apparent on face of record",
            )
        ):
            return part

        stripped = cls._strip_citation_suffix(part)
        if stripped:
            part = stripped

        alias = cls.STATUTE_TOPIC_ALIASES.get(part.casefold()) if allow_alias else None
        alias = cls.STATUTE_TOPIC_ALIASES.get(part.casefold()) if allow_alias else None

        if not is_root and cls.NON_LEAF_BARE_STATUTE_TOPIC_PATTERN.match(
            stripped or part
        ):
            if alias is not None:
                if not alias:
                    return ""
                return alias
            return ""

        if alias is not None:
            if not alias:
                return ""
            part = alias
            if not is_root:
                return part

        if is_root:
            return cls.canonicalise_root_name(part)

        extracted_head = cls._extract_head_topic(part)
        if extracted_head:
            part = extracted_head
            alias = (
                cls.STATUTE_TOPIC_ALIASES.get(part.casefold()) if allow_alias else None
            )
            if alias is not None:
                if not alias:
                    return ""
                return alias

        if part.casefold().startswith(
            (
                "application under ",
                "illegality apparent on face of record",
                "absence of compliant affidavit",
                "absence of assessors' opinions",
                "absence of assessors’ opinions",
                "mandatory requirement to record assessors' opinions",
                "mandatory requirement to record assessors’ opinions",
            )
        ):
            return part

        if "'" in part and part.casefold().endswith(" charge"):
            return ""

        if (
            cls.NON_LEAF_LEADING_NUMERIC_PATTERN.match(part)
            and not allow_leading_numeric
        ):
            return ""

        if not is_root and cls.NON_LEAF_BARE_STATUTE_TOPIC_PATTERN.match(part):
            return ""
        # The following block still runs if is_root=True
        if cls.NON_LEAF_BARE_STATUTE_TOPIC_PATTERN.match(part):
            alias = cls.STATUTE_TOPIC_ALIASES.get(part.casefold())
            if alias is not None:
                if not alias:
                    return ""
                part = alias
            else:
                return ""

        if cls.NON_LEAF_STATUTE_TITLE_PATTERN.match(part):
            alias = cls.STATUTE_TOPIC_ALIASES.get(part.casefold())
            if alias is not None:
                if not alias:
                    return ""
                part = alias
            else:
                return ""

        if cls.NON_LEAF_REFERENCE_ONLY_PATTERN.match(part):
            return ""

        if cls.NON_LEAF_QUOTED_PROPOSITION_PATTERN.match(original_part):
            return ""

        if part.casefold().startswith(("whether ", "when ", "where ", "if ")):
            return part

        if "must reflect charge" in part.casefold():
            return part

        if cls.NON_LEAF_SENTENCE_PROPOSITION_PATTERN.match(part):
            return ""

        if cls.NON_LEAF_DANGLING_FRAGMENT_PATTERN.match(part):
            return ""

        if cls.GENERIC_NON_LEAF_TOPIC_PATTERN.match(part) and not allow_generic_stub:
            return ""

        return part

    @classmethod
    def _extract_head_topic(cls, text):
        separator_match = cls.ONE_WORD_SEPARATOR_HEAD_PATTERN.match(text)
        if (
            separator_match
            and separator_match.group("head").strip().casefold() == "police"
        ):
            head = separator_match.group("head").strip()
            return "Police procedure"

        words = text.split()
        if len(words) < 2:
            return ""

        lower_words = [w.casefold() for w in words]
        if len(words) >= 2:
            if lower_words[1] == "under":
                if lower_words[0] == "application":
                    return ""
                return (
                    " ".join(words[:2]).strip()
                    if len(words) > 2 and lower_words[0] == "revisional"
                    else words[0].strip()
                )
            if lower_words[0] == "revisional" and lower_words[1] == "jurisdiction":
                return " ".join(words[:2]).strip()
            if lower_words[1] in {"requires"}:
                return words[0].strip()
            if (
                len(words) >= 3
                and lower_words[1] == "conviction"
                and lower_words[2]
                in {
                    "quashed",
                    "unsafe",
                    "set",
                }
            ):
                return words[0].strip()
            if (
                lower_words[1] == "v."
                or lower_words[1] == "v"
                or lower_words[1] == "vs"
                or lower_words[1] == "vs."
            ):
                return words[0].strip()
            if (
                lower_words[1] == "and"
                and len(words) >= 3
                and lower_words[2]
                in {
                    "armed",
                    "theft",
                    "violence",
                }
            ):
                return words[0].strip()
            if (
                lower_words[1] == "of"
                and len(words) >= 3
                and lower_words[2]
                in {
                    "girl",
                    "a",
                }
            ):
                return words[0].strip()

        for size in range(1, min(len(words), 4)):
            head_words = words[:size]
            tail = " ".join(words[size:]).strip()
            if not tail:
                continue
            if head_words[0].casefold() in {
                "application",
                "whether",
                "when",
                "where",
                "if",
                "absence",
                "guidelines",
            }:
                continue
            if not cls.HEAD_TOPIC_TRIGGER_PATTERN.match(tail):
                continue

            while head_words and head_words[-1].casefold() in cls.HEAD_TOPIC_STOPWORDS:
                head_words.pop()

            if not head_words:
                continue

            head = " ".join(head_words).strip()
            if len(head) < 4:
                continue

            return head

        return ""

    @staticmethod
    def _dedupe_adjacent_parts(parts):
        deduped = []
        for part in parts:
            if not part:
                continue
            if deduped and deduped[-1].casefold() == part.casefold():
                continue
            deduped.append(part)
        return deduped

    @classmethod
    def canonicalise_root_name(cls, root):
        root = cls._basic_normalise_topic_name(root)
        if not root:
            return ""

        words = root.split()
        if root.casefold() in cls.PRESERVE_LITERAL_ROOTS and any(
            word[:1].isupper() and word.lower() != word for word in words[1:]
        ):
            connector_words = {
                "and",
                "of",
                "the",
                "in",
                "on",
                "for",
                "to",
                "at",
                "by",
                "under",
                "with",
                "or",
            }
            return " ".join(
                word.lower() if word.lower() in connector_words else word
                for word in words
            )

        canonical_words = []
        for index, word in enumerate(words):
            if re.fullmatch(r"[A-Z]{2,}", word):
                canonical_words.append(word)
                continue
            if re.search(r"\d", word):
                canonical_words.append(word)
                continue
            lowered = word.lower()
            if index == 0:
                canonical_words.append(lowered[:1].upper() + lowered[1:])
            else:
                canonical_words.append(lowered)
        return " ".join(canonical_words)

    @classmethod
    def classify_top_level_root(cls, root):
        root = cls.canonicalise_root_name(root)
        if not root:
            return ""

        if root in cls.SAFE_CLASSIFIED_TOP_LEVELS:
            return root

        lowered = root.lower()
        if lowered in {"corporate law", "companies law", "corporations law"}:
            return "Company law"
        if lowered in {"banking", "banker", "bankers' books"}:
            return "Banking law"
        if lowered in {"insurance", "reinsurance law", "marine insurance"}:
            return "Insurance law"
        if lowered in {"customs", "customs & excise", "customs and excise"}:
            return "Customs law"
        if lowered in {"environment", "forest law", "forestry law"}:
            return "Environmental law"
        if lowered in {"wildlife", "wildlife protection"}:
            return "Wildlife law"
        if lowered in {"media", "social media"}:
            return "Media law"
        if lowered in {"telecommunications", "cyber law"}:
            return "Telecommunications law"
        if lowered in {"advocates", "advocate", "advocacy", "legal profession"}:
            return "Legal profession"
        if lowered in {"trust", "trusts", "trust law", "trustees"}:
            return "Trust law"
        if lowered in {
            "elections",
            "electoral law",
            "elections law",
            "election petition",
            "election petitions",
        }:
            return "Election law"
        if lowered in {
            "immigration",
            "citizenship law",
            "nationality law",
            "refugee law",
        }:
            return "Immigration law"
        if lowered in {"criminal procedure", "juvenile procedure"}:
            return "Criminal procedure"
        if lowered == "employment law":
            return "Employment law"
        if lowered == "regional integration law":
            return "Regional integration law"
        if lowered in {"evidence", "evidential law", "evidentiary law"}:
            return "Evidence"
        if lowered in {
            "appeal",
            "appeals",
            "appellate jurisdiction",
            "revisionary powers",
            "revision procedure",
        }:
            return "Appellate practice"
        if cls.GENERIC_CIVIL_ROOT_PATTERN.match(lowered):
            return "Civil procedure"
        if cls.GENERIC_CRIMINAL_ROOT_PATTERN.match(lowered):
            return "Criminal law"
        if cls.GENERIC_LAND_ROOT_PATTERN.match(lowered):
            return "Land law"
        if cls.GENERIC_LABOUR_ROOT_PATTERN.match(lowered):
            return "Labour law"
        if cls.GENERIC_FAMILY_ROOT_PATTERN.match(lowered):
            return "Family law"
        if cls.GENERIC_PROBATE_ROOT_PATTERN.match(lowered):
            return "Probate law"
        if cls.GENERIC_CONTRACT_ROOT_PATTERN.match(lowered):
            return "Contract law"
        return ""

    @classmethod
    def _wrap_under_classified_top_level(cls, parts):
        if not parts:
            return []

        original_root = parts[0]
        original_root_lower = original_root.casefold()
        if (
            cls.NON_LEAF_LEADING_NUMERIC_PATTERN.match(original_root)
            or cls.NON_LEAF_REFERENCE_ONLY_PATTERN.match(original_root)
            or original_root_lower.startswith("article ")
            or re.match(r"^(?:tzs|kshs|usd)\.?\s*[\d,./=-]+", original_root_lower)
        ):
            return []

        classified = cls.infer_top_level_root(parts[0])
        if not classified:
            return []

        if parts[0].casefold() in cls.PRESERVE_LITERAL_ROOTS:
            return parts

        if classified.casefold() == parts[0].casefold():
            return parts

        if classified not in cls.SAFE_CLASSIFIED_TOP_LEVELS:
            return []

        return [classified, parts[0], *parts[1:]]

    @classmethod
    def _expand_long_chain(cls, parts):
        if len(parts) < cls.LONG_CHAIN_PART_THRESHOLD:
            return [parts]

        if any(
            part.casefold().startswith(
                (
                    "whether ",
                    "when ",
                    "submission on ",
                    "suit ",
                    "both parties ",
                )
            )
            for part in parts[2:]
        ):
            return [parts]

        anchor = [parts[0]]
        if len(parts) > 1 and len(parts[1].split()) <= cls.LONG_CHAIN_ANCHOR_WORD_LIMIT:
            anchor.append(parts[1])

        expanded = [anchor]
        start_index = len(anchor)
        previous_fragment = None

        for part in parts[start_index:]:
            if previous_fragment is not None and cls._looks_like_issue_fragment(part):
                expanded.append([*anchor, previous_fragment, part])
                previous_fragment = None
                continue

            if cls._looks_like_issue_fragment(part):
                previous_fragment = part
                expanded.append([*anchor, part])
                continue

            previous_fragment = part
            expanded.append([*anchor, part])

        return expanded

    @classmethod
    def infer_top_level_root(cls, root):
        root = cls.canonicalise_root_name(root)
        if not root:
            return ""

        if root in cls.SAFE_CLASSIFIED_TOP_LEVELS:
            return root

        lowered = root.lower()
        explicit_map = {
            "habeas corpus": "Human rights",
            "evidence": "Criminal law",
            "identification evidence": "Criminal law",
            "documentary evidence": "Criminal law",
            "medical evidence": "Criminal law",
            "credibility": "Criminal law",
            "corroboration": "Criminal law",
            "circumstantial evidence": "Criminal law",
            "sentencing": "Criminal law",
            "sentence": "Criminal law",
            "criminal procedure": "Criminal law",
            "criminal appeal": "Criminal law",
            "appeals": "Civil procedure",
            "appeal": "Civil procedure",
            "appeal procedure": "Appellate practice",
            "appellate review": "Appellate practice",
            "review": "Civil procedure",
            "revision": "Appellate practice",
            "res judicata": "Civil procedure",
            "preliminary objection": "Civil procedure",
            "preliminary objections": "Civil procedure",
            "procedure": "Civil procedure",
            "practice and procedure": "Civil procedure",
            "procedural": "Civil procedure",
            "procedural law": "Civil procedure",
            "procedural fairness": "Civil procedure",
            "procedural irregularity": "Civil procedure",
            "remedy": "Civil procedure",
            "remedies": "Civil procedure",
            "relief": "Civil procedure",
            "interim relief": "Civil procedure",
            "provisional measures": "Civil procedure",
            "government proceedings": "Civil procedure",
            "enforcement": "Civil procedure",
            "pleadings": "Civil procedure",
            "costs": "Civil procedure",
            "taxation of costs": "Civil procedure",
            "delay": "Civil procedure",
            "affidavits": "Civil procedure",
            "overriding objective": "Civil procedure",
            "extension of time": "Civil procedure",
            "labour procedure": "Labour law",
            "employment law": "Employment law",
            "termination of employment": "Labour law",
            "commercial procedure": "Commercial law",
            "company law": "Company law",
            "companies law": "Company law",
            "banking law": "Banking law",
            "contract": "Contract",
            "contract formation": "Contract law",
            "sale of goods": "Contract law",
            "regional integration law": "Regional integration law",
            "natural justice": "Natural Justice",
            "judicial notice": "Judicial Notice",
            "damages": "Damages",
            "trespass": "Trespass",
            "jurisdiction": "Jurisdiction",
            "road/transport law": "Road traffic law",
            "property law": "Land law",
            "land": "Land law",
            "land procedure": "Land law",
            "land dispute": "Land disputes",
            "landlord and tenant": "Land law",
            "mortgage law": "Land law",
            "probate": "Probate law",
            "succession law": "Succession law",
            "matrimonial law": "Family law",
            "matrimonial proceedings": "Family law",
            "matrimonial property": "Family law",
            "taxation": "Tax law",
            "limitation of actions": "Limitation law",
            "limitation": "Limitation law",
            "fair trial": "Human rights",
            "malicious prosecution": "Tort",
            "administrative and procedural law": "Administrative law",
            "parastatal/administrative law": "Administrative law",
            "constitutional/union law": "Constitutional law",
            "land practice and procedure": "Land law",
            "evidence and appellate review": "Civil procedure",
            "extensions of time": "Civil procedure",
            "enlargement of time": "Civil procedure",
            "leave to appeal": "Civil procedure",
            "civil enforcement": "Civil procedure",
            "appellate leave": "Civil procedure",
            "appeal leave": "Civil procedure",
            "assessors’ role": "Criminal law",
            "assessors' role": "Criminal law",
            "assessors’ procedure": "Criminal law",
            "assessors' procedure": "Criminal law",
            "attendance costs": "Civil procedure",
            "appeal requirements": "Civil procedure",
            "necessary party": "Civil procedure",
            "computation": "Civil procedure",
            "evidence chain": "Criminal law",
            "bail quantum": "Criminal law",
            "sentencing illegality": "Criminal law",
            "administrative action and locus standi": "Administrative law",
            "social": "Human rights",
            "insolvency (inability to pay debts; liabilities exceeding assets": "Commercial law",
            "revision as remedy for third-party creditors lacking appeal rights": "Civil procedure",
            "technical vs actual delay (fortunatus masha": "Civil procedure",
            "appellate jurisdiction (s.11(1": "Appellate practice",
            "requirement of dpp consent (s.26(1": "Criminal law",
            "curability under s.127(6": "Criminal law",
            "defective alternative charge (s.311 v s.312": "Criminal law",
            "pcca s.57": "Criminal law",
            "xliii r.2": "Civil procedure",
            "wca s.86(4": "Labour law",
            "wca s.101": "Labour law",
            "ord. 1937, s. 23": "Civil procedure",
            "leave to appeal (s.47 ldca": "Civil procedure",
        }
        if lowered in explicit_map:
            return explicit_map[lowered]
        if re.search(
            r"\b(?:advocate|advocates|advocacy|remuneration|taxing master|"
            r"instruction fee|professional ethics|conflict of interest|"
            r"advocate-client|holding brief|practising certificate|legal profession)\b",
            lowered,
        ):
            return "Legal profession"
        if re.search(
            r"\b(?:appealability|appellate|retrial|revisionary|revision procedure|"
            r"certification of point of law|certificate of point of law|"
            r"leave stage|single justice)\b",
            lowered,
        ):
            return "Appellate practice"
        if re.search(
            r"\b(?:evidence|evidential|evidentiary|corroboration|adverse inference|"
            r"burden|onus|proof|cross-examination|hearsay|dying declaration|"
            r"hostile witness|exhibit|documentary requirements)\b",
            lowered,
        ):
            return "Evidence"
        if re.search(
            r"\b(?:habeas corpus|detention|illegal detention|torture|fair trial|"
            r"basic rights|access to justice|human dignity|freedom of religion|"
            r"prohibition of discrimination|rights of detained suspects)\b",
            lowered,
        ):
            return "Human rights"
        if re.search(
            r"\b(?:judicial review|certiorari|mandamus|prohibition|reviewability)\b",
            lowered,
        ):
            return "Judicial review"
        if re.search(
            r"\b(?:election|electoral|election petition|election petitions|corrupt practices elections)\b",
            lowered,
        ):
            return "Election law"
        if re.search(
            r"\b(?:immigration|citizenship|nationality|refugee|deportation|special pass)\b",
            lowered,
        ):
            return "Immigration law"
        if re.search(
            r"\b(?:insurance|policyholder|indemnity|yellow card|bancassurance|reinsurance)\b",
            lowered,
        ):
            return "Insurance law"
        if re.search(
            r"\b(?:banking|banker|letters of credit|documentary credits|"
            r"secured lending|credit reporting|microfinance|syndicated lending|"
            r"bills of exchange|cheque law)\b",
            lowered,
        ):
            return "Banking law"
        if re.search(
            r"\b(?:company|corporate|shares|shareholder|winding up|liquidation|"
            r"close corporations|business names|registered office|"
            r"directors[’']?|salomon)\b",
            lowered,
        ):
            return "Company law"
        if re.search(
            r"\b(?:trade mark|trademark|passing off|copyright|domain names?|"
            r"patent|image rights|digital rights|well-known marks)\b",
            lowered,
        ):
            return "Intellectual property law"
        if re.search(r"\b(?:competition law|restraint of trade)\b", lowered):
            return "Competition law"
        if re.search(
            r"\b(?:public procurement|procurement|tender law|tender procedure|auctioneer licensing)\b",
            lowered,
        ):
            return "Procurement law"
        if re.search(
            r"\b(?:customs|tariff|excise|stamp duty|exchange control|import duty|"
            r"export control|eaccma|customs classification)\b",
            lowered,
        ):
            return "Customs law"
        if re.search(
            r"\b(?:environmental|forest|forestry|pollution|planning law|sustainable development)\b",
            lowered,
        ):
            return "Environmental law"
        if re.search(r"\b(?:wildlife|fauna|national parks?|trophies)\b", lowered):
            return "Wildlife law"
        if re.search(
            r"\b(?:mining|minerals?|prospecting licence|mining licence)\b", lowered
        ):
            return "Mining law"
        if re.search(
            r"\b(?:maritime|admiralty|carriage by sea|charterparty|bill[s]? of lading|ports law|marine transport)\b",
            lowered,
        ):
            return "Maritime law"
        if re.search(
            r"\b(?:road traffic|street traffic|motor vehicle|motor-vehicle|"
            r"traffic law|road law|careless driving|driving licence "
            r"disqualification)\b",
            lowered,
        ):
            return "Road traffic law"
        if re.search(
            r"\b(?:water law|energy and water|electricity|electricity supply|utility law)\b",
            lowered,
        ):
            return "Water law"
        if re.search(
            r"\b(?:telecommunications|cyber|electronic communications|electronic transactions|data protection)\b",
            lowered,
        ):
            return "Telecommunications law"
        if re.search(
            r"\b(?:media|newspapers|broadcasting law|publication by media|media standard)\b",
            lowered,
        ):
            return "Media law"
        if re.search(r"\b(?:sports law|sports association law)\b", lowered):
            return "Sports law"
        if re.search(
            r"\b(?:education law|higher education|university law|academic misconduct|academic decisions)\b",
            lowered,
        ):
            return "Education law"
        if re.search(
            r"\b(?:health law|medical discipline|medical council|health care rights|"
            r"mental health law|medical schemes)\b",
            lowered,
        ):
            return "Health law"
        if re.search(r"\b(?:prison|prisons|prisoners)\b", lowered):
            return "Prison law"
        if re.search(
            r"\b(?:customary|native law and custom|sungusungu|operation vijiji|village council)\b",
            lowered,
        ):
            return "Customary law"
        if re.search(
            r"\b(?:islamic|mohammedan|muslim law|wakf|waqf|sharia)\b", lowered
        ):
            return "Islamic law"
        if re.search(
            r"\b(?:international organisations?|diplomatic immunity|"
            r"consular immunities|african commission|eac treaty|maputo protocol|"
            r"eacj|international humanitarian law)\b",
            lowered,
        ):
            return "International law"
        if re.search(
            r"\b(?:conflict of laws|private international law|forum conveniens|"
            r"forum selection|choice-of-law)\b",
            lowered,
        ):
            return "Conflict of laws"
        if re.search(
            r"\b(?:trust law|trusts?|trustee|trustees|fiduciary duties|charitable institution)\b",
            lowered,
        ):
            return "Trust law"
        if re.search(
            r"\b(?:witness|voir dire|forensic|confession|confessions|corroborat|"
            r"credib|medical report|pf3|eyewitness)\b",
            lowered,
        ):
            return "Evidence"
        if re.search(
            r"\b(?:murder|manslaughter|theft|robbery|rape|burglary|drugs?|"
            r"narcotics?|search and seizure|plea of guilty|guilty plea|"
            r"armed robbery)\b",
            lowered,
        ):
            return "Criminal law"
        if re.search(
            r"\b(?:validity of|burden remains|misapplication of|requirement to|"
            r"interpretation and application of|effect of|principle of|"
            r"section \d+|sections \d+)\b",
            lowered,
        ):
            return "Civil procedure"
        if re.search(
            r"\b(?:fair hearing|review|jurisdiction|hearing|pleadings?|costs?|"
            r"affidavit|extension|notice|application|filing|stay|recusal)\b",
            lowered,
        ):
            return "Civil procedure"
        if re.search(
            r"\b(?:trial procedure|trial irregularity|interlocutory relief|"
            r"interlocutory injunctions?|judicial discretion|"
            r"exercise of judicial discretion|representative suits?|joinder|"
            r"non-joinder|appealability|appellate powers|appellate practice|"
            r"trial fairness|right to be heard|summary proceedings|"
            r"pre-trial conference|certificate of urgency)\b",
            lowered,
        ):
            return "Civil procedure"
        if re.search(
            r"\b(?:abuse of process|good cause|consequence|principle|procedural law|"
            r"appellate|amendment|remittal|nullity|parties|mitigation|precedents?|"
            r"appellate relief|judicial impartiality|statutory construction|"
            r"trial procedure|civil practice|ex parte proceedings|administration|"
            r"jurisdictional defect|restoration|urgency|counterclaim|case law|"
            r"authority|public policy|balance of convenience|adjournment|"
            r"prematurity|finality of litigation|taxation reference|"
            r"instruction fees|reference procedure|quashing and remittal|"
            r"forum shopping|delay|promptness|competence|competency|"
            r"discretion(?:ary)? relief|interpretation)\b",
            lowered,
        ):
            return "Civil procedure"
        if re.search(
            r"\b(?:inheritance|succession|administrator|administratrix|estate|wills?|probate)\b",
            lowered,
        ):
            return "Probate law"
        if re.search(
            r"\b(?:intestacy|executor|executrix|letters of administration|"
            r"presumption of death|testamentary|heirs?|"
            r"revocation of administrators)\b",
            lowered,
        ):
            return "Succession law"
        if re.search(
            r"\b(?:family|matrimonial|husband|wife|child|children|customary marriage)\b",
            lowered,
        ):
            return "Family law"
        if re.search(
            r"\b(?:adultery|marriage|paternity|adoption|domestic violence|cohabitation|alimony|next friend)\b",
            lowered,
        ):
            return "Family law"
        if re.search(
            r"\b(?:contract|security|guarantee|partnership|sale of goods|loan|lease financing|promissory note)\b",
            lowered,
        ):
            return "Contract law"
        if re.search(
            r"\b(?:commercial|negotiable instruments|agency law|agency agreement|"
            r"lease agreement|business licensing|trade unions?)\b",
            lowered,
        ):
            return "Commercial law"
        if re.search(
            r"\b(?:company|commercial|insolv|cooperative|co-operative|societies|society|bank|bankruptcy|liquidator)\b",
            lowered,
        ):
            return "Commercial law"
        if re.search(
            r"\b(?:land|tenant|mortgage|title|property|housing|sale by auction|"
            r"auction sale|transfer|ward development|urban planning|"
            r"local government|village law)\b",
            lowered,
        ):
            return "Land law"
        if re.search(
            r"\b(?:adverse possession|rent law|rent restriction|tenancy law|"
            r"landlord|lease law|bona fide purchaser|valuation|mortgages?|"
            r"road reserve|right of occupancy|carriage by road)\b",
            lowered,
        ):
            return "Land law"
        if re.search(
            r"\b(?:transport law|carriage of goods|carriage by air|carriage by rail|"
            r"carriage and clearing agents|warehouse receipts)\b",
            lowered,
        ):
            return "Commercial law"
        if re.search(
            r"\b(?:administrative|parastatal|public law|prerogative|certiorari|mandamus|locus standi)\b",
            lowered,
        ):
            return "Administrative law"
        if re.search(
            r"\b(?:public corporations?|government|authorities|ward tribunals?|"
            r"regional integration|east african community|african community|"
            r"electoral commission|public employment|public administration|"
            r"municipal|local government law|district council|attorney general|"
            r"public officers?)\b",
            lowered,
        ):
            return "Administrative law"
        if re.search(
            r"\b(?:constitutional|bill of rights|fundamental rights|equality before the law)\b",
            lowered,
        ):
            return "Constitutional law"
        if re.search(
            r"\b(?:human rights|peoples['’] rights|african charter|"
            r"freedom of expression|socio-economic rights|access to justice|"
            r"dignity|equality|right to dignity|right to life|"
            r"liberté de réunion)\b",
            lowered,
        ):
            return "Human rights"
        if re.search(r"\b(?:tax|vat|income tax|taxing officer|tra)\b", lowered):
            return "Tax law"
        if re.search(r"\b(?:defamation|libel|slander)\b", lowered):
            return "Defamation"
        if re.search(
            r"\b(?:malicious prosecution|negligence|compensation|damages|delict|tort)\b",
            lowered,
        ):
            return "Tort"
        if re.search(
            r"\b(?:civil liability|vicarious liability|product liability|"
            r"occupiers['’]? liability|motor vehicle accidents?|"
            r"road traffic accident|road accident|civil wrongs|personal injury|"
            r"assault|torts?)\b",
            lowered,
        ):
            return "Tort"
        if re.search(r"\b(?:arbitration|arbitral)\b", lowered):
            return "Arbitration"
        if re.search(
            r"\b(?:admissibility|identification|bail|sentence|sentencing|"
            r"criminal appeal|sexual offences|wildlife offences)\b",
            lowered,
        ):
            return "Criminal law"
        if re.search(
            r"\b(?:defence of alibi|alibi|hearsay|exhibits|forgery|fraud|"
            r"economic crimes?|penal law|recent possession|mens rea|homicide|"
            r"prosecution duty|witnesses|magistrates|terrorism|drug trafficking|"
            r"narcotic drugs|defences?|prosecution conduct|reasonable doubt|"
            r"forensics|admissions|theft by public servant|intoxication|"
            r"wildlife conservation|presumption of innocence|"
            r"prosecutorial discretion|housebreaking|burglary|corruption|"
            r"murder|manslaughter|theft|robbery|drugs|weapons|charge|conviction)\b",
            lowered,
        ):
            return "Criminal law"
        if "/" in lowered:
            if any(
                token in lowered
                for token in ("customary", "matrimonial", "inheritance", "probate")
            ):
                return "Probate law"
            if any(token in lowered for token in ("contract", "guarantee")):
                return "Contract law"
            if any(token in lowered for token in ("bank", "banking")):
                return "Banking law"
            if any(token in lowered for token in ("commercial",)):
                return "Commercial law"
            if any(token in lowered for token in ("company", "corporate")):
                return "Company law"
            if any(
                token in lowered
                for token in ("land", "property", "ward development", "housing")
            ):
                return "Land law"
            if any(token in lowered for token in ("administrative",)):
                return "Administrative law"
            if any(token in lowered for token in ("constitutional",)):
                return "Constitutional law"
            if any(token in lowered for token in ("public", "municipal")):
                return "Administrative law"
            if any(token in lowered for token in ("road", "transport")):
                return "Road traffic law"
            if any(
                token in lowered for token in ("labour", "employment", "industrial")
            ):
                return "Labour law"
        if cls.CIVIL_REFERENCE_ROOT_PATTERN.match(lowered):
            return "Civil procedure"
        if cls.CRIMINAL_REFERENCE_ROOT_PATTERN.match(lowered):
            return "Criminal law"
        if cls.ADMINISTRATIVE_REFERENCE_ROOT_PATTERN.match(lowered):
            return "Administrative law"
        if cls.LAND_REFERENCE_ROOT_PATTERN.match(lowered):
            return "Land law"
        if cls.PROBATE_REFERENCE_ROOT_PATTERN.match(lowered):
            return "Probate law"
        if cls.CONTRACT_REFERENCE_ROOT_PATTERN.match(lowered):
            return "Contract law"
        if cls.COMMERCIAL_REFERENCE_ROOT_PATTERN.match(lowered):
            return "Commercial law"
        if re.search(
            r"\b(?:appeal|revision|judgment|decree|costs?|computation|delay|"
            r"party|mediation|notice|filing|compliance)\b",
            lowered,
        ):
            return "Civil procedure"
        if re.search(
            r"\b(?:charge|conviction|bail|confession|offence|offences|forfeiture|trespass|criminal|dpp|assessors?)\b",
            lowered,
        ):
            return "Criminal law"
        if re.search(
            r"\b(?:administrative|locus standi|prerogative|judicial review)\b", lowered
        ):
            return "Administrative law"
        if re.search(
            r"\b(?:land|mortgage|housing|property|tenant|title|urban planning)\b",
            lowered,
        ):
            return "Land law"
        classified = cls.classify_top_level_root(root)
        if classified in cls.SAFE_CLASSIFIED_TOP_LEVELS:
            return classified
        return ""

    @classmethod
    def _looks_like_issue_fragment(cls, part):
        text = part.strip()
        if not text:
            return False

        if cls.ISSUE_FRAGMENT_PATTERN.match(text):
            return True

        if len(text.split()) <= 6 and text[:1].isupper():
            return True

        return False


class FlynoteUpdater:
    """Manages the Flynote tree for flynote-derived topics.

    Builds (or reuses) ``Flynote`` nodes for each path segment, and creates
    ``JudgmentFlynote`` links so that the judgment appears under the correct
    leaf topics. Uses treebeard's MP_Node for tree management.

    Usage::

        updater = FlynoteUpdater()
        updater.update_for_judgment(judgment)
    """

    def __init__(self):
        self.parser = FlynoteParser()
        self.node_cache = {}

    def get_or_create_node(self, parent, name):
        """Find an existing Flynote whose slug matches, or create a new one.

        *parent* is the parent Flynote node, or None for top-level.

        Returns ``(node, defer_reason)`` where ``defer_reason`` is set when the
        whole relink should be retried later. ``node`` is ``None`` when the
        name produces an empty slug and the current path should be skipped.
        """
        normalised = FlynoteParser.normalise_name(name)
        if not normalised:
            return None, None

        if parent:
            expected_slug = f"{parent.slug}-{normalised}"
        else:
            expected_slug = normalised

        cached = self.node_cache.get(expected_slug)
        if cached is not None:
            return cached, None

        existing = Flynote.objects.filter(slug=expected_slug).first()
        if existing:
            self.node_cache[expected_slug] = existing
            return existing, None

        if not parent:
            try:
                node = Flynote.add_root(name=name, slug=expected_slug)
                self.node_cache[expected_slug] = node
                return node, None
            except IntegrityError:
                existing = Flynote.objects.filter(slug=expected_slug).first()
                if existing:
                    self.node_cache[expected_slug] = existing
                return existing, None

        for attempt in range(1, 4):
            locked_parent = (
                Flynote.objects.select_for_update()
                .filter(pk=parent.pk)
                .only("id", "slug", "path", "depth", "numchild")
                .first()
            )
            if not locked_parent:
                return (
                    None,
                    "parent %s no longer exists while creating '%s'"
                    % (parent.pk, expected_slug),
                )

            try:
                node = locked_parent.add_child(name=name, slug=expected_slug)
                self.node_cache[expected_slug] = node
                return node, None
            except IntegrityError:
                existing = Flynote.objects.filter(slug=expected_slug).first()
                if existing:
                    self.node_cache[expected_slug] = existing
                return existing, None
            except AttributeError as exc:
                if "add_sibling" not in str(exc):
                    raise

                existing = Flynote.objects.filter(slug=expected_slug).first()
                if existing:
                    self.node_cache[expected_slug] = existing
                    return existing, None

                if attempt == 3:
                    return (
                        None,
                        "Treebeard could not safely create '%s' after %s retries"
                        % (expected_slug, attempt),
                    )

    @transaction.atomic
    def update_for_judgment(self, judgment, refresh_counts=False):
        """Parse a judgment's flynote and sync its Flynote links.

        1. Parses ``judgment.flynote`` into hierarchical paths.
        2. For each path, walks (or creates) ``Flynote`` nodes from root to leaf.
        3. Replaces existing ``JudgmentFlynote`` links with the rebuilt leaf set.
        4. Links the judgment to the leaf node of every path.

        Does nothing if the flynote text cannot be parsed (plain prose, empty, etc.).
        """
        overall_start = perf_counter()

        parse_start = perf_counter()
        try:
            paths = self.parser.parse(judgment.flynote)
        except IndexError:
            log.warning(
                "Skipping flynote update for judgment %s because parsing hit an indexing error. Flynote excerpt: %r",
                judgment.pk,
                (judgment.flynote or "")[:200],
                exc_info=True,
            )
            return
        parse_ms = (perf_counter() - parse_start) * 1000

        if not paths:
            JudgmentFlynote.objects.filter(document=judgment).delete()
            log.info(
                "Linked judgment %s to 0 flynote topics (parse=%.2fms, nodes=0.00ms, links=0.00ms, total=%.2fms).",
                judgment.pk,
                parse_ms,
                (perf_counter() - overall_start) * 1000,
            )
            return

        node_start = perf_counter()
        leaf_flynotes = set()
        roots_to_refresh = set()
        for path in paths:
            parent = None
            root_id = None
            for index, name in enumerate(path):
                node, defer_reason = self.get_or_create_node(parent, name)
                if defer_reason:
                    log.warning(
                        "Skipping flynote update for judgment %s because "
                        "tree rebuilding could not be completed safely: %s",
                        judgment.pk,
                        defer_reason,
                    )
                    transaction.set_rollback(True)
                    return
                if node is None:
                    break
                if index == 0:
                    root_id = node.pk
                parent = node
            else:
                leaf_flynotes.add(node)
                if root_id is not None:
                    roots_to_refresh.add(root_id)
        node_ms = (perf_counter() - node_start) * 1000

        JudgmentFlynote.objects.filter(document=judgment).delete()

        link_start = perf_counter()
        JudgmentFlynote.objects.bulk_create(
            [
                JudgmentFlynote(document=judgment, flynote=flynote)
                for flynote in leaf_flynotes
            ],
            ignore_conflicts=True,
        )
        link_ms = (perf_counter() - link_start) * 1000

        log.info(
            "Linked judgment %s to %s flynote topics (parse=%.2fms, nodes=%.2fms, links=%.2fms, total=%.2fms).",
            judgment.pk,
            len(leaf_flynotes),
            parse_ms,
            node_ms,
            link_ms,
            (perf_counter() - overall_start) * 1000,
        )

        if refresh_counts and leaf_flynotes:
            for root_id in roots_to_refresh:
                refresh_flynote_document_count(root_id, schedule=30 * 60)
