import logging

from django.db import transaction

from peachjam.models import Judgment

from .offence import OffenceMatcher, OffenceMentionExtractor
from .sentence import SentenceExtractor

log = logging.getLogger(__name__)


class CriminalDataExtractor:
    """
    Orchestrates all extraction stages in order.

    Each stage must inherit from BaseExtractor.
    """

    def __init__(self, judgment: Judgment):
        self.judgment = judgment
        self.stages = [
            OffenceMentionExtractor,
            OffenceMatcher,
            SentenceExtractor,
        ]

    def run(self):
        log.info(f"Starting criminal extraction for judgment {self.judgment.id}")

        with transaction.atomic():
            for stage_cls in self.stages:
                stage_name = stage_cls.__name__
                log.info(f"Running stage: {stage_name}")

                stage = stage_cls(judgment=self.judgment)
                stage.run()

                log.info(f"Completed stage: {stage_name}")

        log.info(f"Criminal data extraction complete for judgment {self.judgment.id}")
        return self.judgment
