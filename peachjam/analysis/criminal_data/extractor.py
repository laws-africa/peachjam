import logging

from django.db import transaction

from peachjam.models import Judgment

from .case_type import CaseTypeExtractor
from .filing_year import FilingYearExtractor
from .offence import OffenceMatcher, OffenceMentionExtractor
from .sentence import SentenceExtractor

log = logging.getLogger(__name__)


class CriminalDataExtractor:
    """
    Orchestrates all extraction stages in order.

    Each stage must inherit from BaseExtractor.
    """

    def __init__(self, judgment: Judgment, force: bool = False):
        self.judgment = judgment
        self.force = force
        self.stages = [
            OffenceMentionExtractor,
            OffenceMatcher,
            SentenceExtractor,
            FilingYearExtractor,
        ]

    def run(self):
        log.info(f"Starting criminal extraction for judgment {self.judgment.id}")

        with transaction.atomic():

            case_type = CaseTypeExtractor(self.judgment).run()

            if case_type != "criminal" and not self.force:
                log.info(
                    f"{self.judgment} is not criminal, skipping criminal data extraction."
                )
                return self.judgment

            if self.force and case_type != "criminal":
                log.info(
                    f"Forcing criminal data extraction for {self.judgment}: case type: {case_type}"
                )

            for stage_cls in self.stages:
                stage_name = stage_cls.__name__
                log.info(f"Running stage: {stage_name}")

                stage = stage_cls(judgment=self.judgment)
                stage.run()

                log.info(f"Completed stage: {stage_name}")

        log.info(f"Criminal data extraction complete for judgment {self.judgment.id}")
        return self.judgment
