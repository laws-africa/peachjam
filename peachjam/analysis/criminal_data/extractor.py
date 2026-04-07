import logging
import os

from django.db import transaction

from peachjam.models import (
    CaseTag,
    Judgment,
    JudgmentOffence,
    Offence,
    Outcome,
    Sentence,
)

from .agent import (
    extract_case_type_filing_year,
    extract_offences_and_sentences,
    extract_outcomes,
)
from .vocabulary import JUDGMENT_OFFENCE_CASE_TAGS, normalize_tag_array

log = logging.getLogger(__name__)


class CriminalDataExtractor:
    """
    Runs extraction and saves results to the DB.
    """

    def __init__(self):
        if not os.environ.get("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY is not configured.")

    @transaction.atomic
    def extract(self, judgment: Judgment):
        judgment_text = judgment.get_content_as_text()
        meta_out = extract_case_type_filing_year(judgment_text)

        if meta_out.case_type is not None:
            judgment.case_type = meta_out.case_type

        if meta_out.filing_year is not None:
            judgment.filing_year = meta_out.filing_year

        judgment.save(update_fields=["case_type", "filing_year"])

        # clear old extracted criminal data first
        Sentence.objects.filter(judgment=judgment).delete()
        JudgmentOffence.objects.filter(judgment=judgment).delete()
        judgment.outcomes.clear()

        # criminal judgments should get offence/sentence extraction
        if judgment.case_type != Judgment.CaseType.CRIMINAL:
            return None, meta_out

        offence_out = extract_offences_and_sentences(judgment_text)
        outcome_out = extract_outcomes(judgment_text)

        outcome_names = set()
        for outcome_match in outcome_out.outcomes:
            outcome_names.add(outcome_match.extracted_outcome)

        if outcome_names:
            matched_outcomes = Outcome.objects.filter(name__in=outcome_names)
            matched_names = set(matched_outcomes.values_list("name", flat=True))
            missing_names = outcome_names - matched_names
            for missing_name in sorted(missing_names):
                log.info(
                    "extracted outcome %s not found in canonical outcomes", missing_name
                )

            judgment.outcomes.set(matched_outcomes)

        for match in offence_out.offences:
            if match.offence_id is None:
                log.info(
                    f"extracted offence {match.extracted_offence} not matched to offence"
                )
                continue

            offence = Offence.objects.get(id=match.offence_id)
            normalized_case_tags = normalize_tag_array(match.case_tags)
            case_tags = normalize_tag_array(
                match.case_tags, allowed_tags=JUDGMENT_OFFENCE_CASE_TAGS
            )
            invalid_case_tags = [
                tag
                for tag in normalized_case_tags
                if tag not in JUDGMENT_OFFENCE_CASE_TAGS
            ]

            if invalid_case_tags:
                log.warning(
                    "dropping invalid case tags for offence %s on judgment %s: %s",
                    offence.id,
                    judgment.id,
                    invalid_case_tags,
                )

            case_tag_map = CaseTag.objects.in_bulk(case_tags, field_name="name")
            matched_case_tags = [
                case_tag_map[name] for name in case_tags if name in case_tag_map
            ]
            missing_case_tags = [name for name in case_tags if name not in case_tag_map]

            if missing_case_tags:
                log.warning(
                    "canonical case tags missing from DB for offence %s on judgment %s: %s",
                    offence.id,
                    judgment.id,
                    missing_case_tags,
                )

            jo = JudgmentOffence.objects.create(
                judgment=judgment,
                offence=offence,
            )
            jo.tags.set(matched_case_tags)
            persisted_case_tags = [tag.name for tag in matched_case_tags]
            log.info("Created %s with case tags %s", jo, persisted_case_tags)

            for s in match.sentences:
                sentence = Sentence.objects.create(
                    judgment=judgment,
                    offence=jo,
                    sentence_type=s.sentence_type,
                    duration_months=s.duration_months,
                    fine_amount=s.fine_amount,
                    suspended=s.suspended,
                    mandatory_minimum=s.mandatory_minimum,
                )
                log.info(f"Created {sentence}")

        return offence_out, outcome_out, meta_out
