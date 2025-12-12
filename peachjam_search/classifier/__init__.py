import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

log = logging.getLogger(__name__)


class QueryLabel(Enum):
    EMPTY = "empty"
    TOO_SHORT = "too_short"
    ACT_NAME = "act_name"
    ACT_NUMBER = "act_number"
    ACT_SECTION = "act_section"
    CASE_NAME = "case_name"
    CASE_NUMBER = "case_number"
    GAZETTE_NUMBER = "gazette_number"
    LEGAL_TERM = "legal_term"
    NUMBERS = "numbers"
    QUOTE = "quote"


@dataclass
class QueryClass:
    query: str
    query_clean: Optional[str] = None
    n_chars: Optional[int] = None
    n_words: Optional[int] = None
    label: Optional[QueryLabel] = None
    confidence: Optional[float] = None


class QueryClassifier:
    """This classifies queries into predefined categories using rules and a simple ML model."""

    # leading non-word characters
    LEADING_JUNK_RE = re.compile(r"^[^\w]+")
    CONFIDENCE_THRESHOLD = 0.7

    def classify(self, query: str) -> QueryClass:
        qclass = self.clean_query(query)

        self.classify_with_rules(qclass)
        if not qclass.label:
            self.classify_with_model(qclass)

        return qclass

    def clean_query(self, query: str) -> QueryClass:
        qclass = QueryClass(query)

        query = query.strip()
        query = self.LEADING_JUNK_RE.sub("", query).lstrip()
        qclass.query_clean = query

        # add some useful statistics
        qclass.n_chars = len(query)
        qclass.n_words = len(query.split())

        return qclass

    def classify_with_rules(self, qclass: QueryClass):
        """Fixed classifications based on simple rules.
        numbers: 99, 99a, 55 2
        fixed list of classifications for 1-2 word queries?
        """
        if qclass.n_chars == 0:
            qclass.label = QueryLabel.EMPTY
            qclass.confidence = 1.0

        elif qclass.n_chars < 2 or qclass.n_words < 2:
            qclass.label = QueryLabel.TOO_SHORT
            qclass.confidence = 1.0

        # long queries are usually cut-and-paste quotes
        elif qclass.n_words >= 40:
            qclass.label = QueryLabel.QUOTE
            qclass.confidence = 1.0

    def classify_with_model(self, qclass: QueryClass):
        """Attempt to classify the query via the ML model if the rules failed."""
        try:
            from .ml_classifier import get_ml_classifier
        except ImportError as e:
            log.warning(
                "ML classifier module not available, skipping ML classification.",
                exc_info=e,
            )
            return

        try:
            ml_classifier = get_ml_classifier()
        except FileNotFoundError as e:
            log.warning(
                "ML classifier model file not found, skipping ML classification.",
                exc_info=e,
            )
            return

        predictions = ml_classifier.predict_queries([qclass.query_clean or ""])
        if len(predictions) == 1:
            label, confidence = predictions[0]
            if confidence >= self.CONFIDENCE_THRESHOLD:
                qclass.label = QueryLabel(label)
                qclass.confidence = confidence
