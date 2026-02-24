import logging
from typing import List, Type

from django.db import transaction

from peachjam.models import Judgment

from .base import BaseExtractor

log = logging.getLogger(__name__)


class CriminalDataExtractionPipeline:
    """
    Orchestrates all extraction stages in order.

    Each stage must inherit from BaseExtractionService.
    """

    default_stages: List[Type[BaseExtractor]] = []

    def __init__(
        self, judgment: Judgment, stages: List[Type[BaseExtractor]] | None = None
    ):
        self.judgment = judgment
        self.stages = stages or self.default_stages

    def run(self):
        log.info(f"Starting extraction pipeline for judgment {self.judgment.id}")

        with transaction.atomic():
            for stage_cls in self.stages:
                stage_name = stage_cls.__name__
                log.info(f"Running stage: {stage_name}")

                stage = stage_cls(judgment=self.judgment)
                stage.run()

                log.info(f"Completed stage: {stage_name}")

        log.info(f"Pipeline complete for judgment {self.judgment.id}")
        return self.judgment
