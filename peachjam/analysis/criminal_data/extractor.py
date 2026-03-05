from django.db import transaction

from peachjam.models import Judgment, JudgmentOffence, Offence
from peachjam.models import Sentence as SentenceModel

from .agent import extract_case_type_filing_year, extract_offences_and_sentences


class JudgmentExtractionService:
    """
    Runs extraction and saves results to the DB.
    """

    @transaction.atomic
    def extract(self, judgment: Judgment, judgment_text: str):
        offence_out = extract_offences_and_sentences(judgment_text)
        meta_out = extract_case_type_filing_year(judgment_text)

        # Update Judgment meta
        if meta_out.case_type is not None:
            judgment.case_type = meta_out.case_type  # matches Judgment.CaseType values
        if meta_out.filing_year is not None:
            judgment.filing_year = meta_out.filing_year
        judgment.save(update_fields=["case_type", "filing_year"])

        # Persist offences + sentences
        # (You might want to delete existing extracted rows first, depending on your pipeline)
        # JudgmentOffence.objects.filter(judgment=judgment, source="llm").delete()

        for match in offence_out.offences:
            if match.offence_id is None:
                continue  # skip unmatched if that’s your desired behavior

            offence = Offence.objects.get(id=match.offence_id)

            jo = JudgmentOffence.objects.create(
                judgment=judgment,
                offence=offence,
                extracted_label=match.extracted_offence,
                basis=match.basis,
                # source="llm",  # if you track provenance
            )

            for s in match.sentences:
                SentenceModel.objects.create(
                    judgment_offence=jo,
                    sentence_type=s.sentence_type,
                    duration_months=s.duration_months,
                    fine_amount=s.fine_amount,
                    suspended=s.suspended,
                    mandatory_minimum=s.mandatory_minimum,
                    basis=s.basis,
                )

        return offence_out, meta_out
