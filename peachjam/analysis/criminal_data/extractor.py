import logging
import os

from django.db import transaction

from peachjam.models import Judgment, JudgmentOffence, Offence, Sentence

from .agent import extract_case_type_filing_year, extract_offences_and_sentences

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

        # criminal judgments should get offence/sentence extraction
        if judgment.case_type != Judgment.CaseType.CRIMINAL:
            return None, meta_out

        offence_out = extract_offences_and_sentences(judgment_text)

        for match in offence_out.offences:
            if match.offence_id is None:
                log.info(
                    f"extracted offence {match.extracted_offence} not matched to offence"
                )
                continue

            offence = Offence.objects.get(id=match.offence_id)

            jo = JudgmentOffence.objects.create(
                judgment=judgment,
                offence=offence,
            )
            log.info(f"Created {jo}")

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

        return offence_out, meta_out
