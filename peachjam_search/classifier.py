import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import joblib
import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split


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


class ModelQueryClassifier:
    """Trains and uses a machine learning model to classify queries."""

    MODEL_PATH = Path(__file__).parent / "ml_models" / "query_classifier_model.joblib"
    model_bundle = None

    def load_model(self, model_path: Path = MODEL_PATH) -> dict:
        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}.")
        self.model_bundle = joblib.load(model_path)

    def predict_queries(self, queries: Sequence[str]) -> List[Tuple[str, float]]:
        if not queries:
            return []

        processed_queries = self.preprocess_queries(queries)
        vectorizer: TfidfVectorizer = self.model_bundle["vectorizer"]
        classifier: LogisticRegression = self.model_bundle["classifier"]
        word_stats: dict = self.model_bundle["word_count_stats"]

        features, _ = self.build_feature_matrix(
            processed_queries,
            vectorizer=vectorizer,
            word_stats=word_stats,
            fit_vectorizer=False,
        )
        probabilities = classifier.predict_proba(features)
        best_idx = np.argmax(probabilities, axis=1)
        labels = classifier.classes_[best_idx]
        confidences = probabilities[np.arange(len(queries)), best_idx]
        return list(zip(labels, confidences))

    def build_vectorizer(self) -> TfidfVectorizer:
        return TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(1, 3),
            lowercase=True,
            strip_accents="unicode",
        )

    def word_counts_feature(
        self,
        queries: Sequence[str],
        stats: dict | None = None,
    ) -> Tuple[sparse.csr_matrix, dict]:
        counts = np.array(
            [len(str(q).split()) for q in queries],
            dtype=np.float32,
        ).reshape(-1, 1)

        if stats is None:
            mean = float(counts.mean())
            std = float(counts.std())
            if std == 0.0:
                std = 1.0
            stats = {"mean": mean, "std": std}

        normalized = (counts - stats["mean"]) / stats["std"]
        return sparse.csr_matrix(normalized), stats

    def build_feature_matrix(
        self,
        queries: Sequence[str],
        vectorizer: TfidfVectorizer,
        word_stats: dict | None = None,
        fit_vectorizer: bool = False,
    ) -> Tuple[sparse.csr_matrix, dict]:
        if fit_vectorizer:
            tfidf = vectorizer.fit_transform(queries)
        else:
            tfidf = vectorizer.transform(queries)

        stats_input = None if fit_vectorizer else word_stats
        if stats_input is None and not fit_vectorizer:
            raise ValueError("word_stats must be provided when fit_vectorizer=False")

        word_feature, stats = self.word_counts_feature(queries, stats=stats_input)
        combined = sparse.hstack([tfidf, word_feature], format="csr")

        return combined, stats

    def preprocess_query(self, text: str) -> str:
        text = text.strip()
        # replace digits with N
        return re.sub(r"\d", "N", str(text))

    def preprocess_queries(self, queries: Sequence[str]) -> List[str]:
        return [self.preprocess_query(q) for q in queries]

    def pre_clean_raw_data(self, data: pd.DataFrame):
        """Clean up raw data exported from openrefine, used when training."""
        # change search_clean column name to query if exists
        if "search_clean" in data.columns:
            data.rename(columns={"search_clean": "query"}, inplace=True)

        # change search_classification column name to label if exists
        if "search_classification" in data.columns:
            data.rename(columns={"search_classification": "label"}, inplace=True)

        # remove duplicate rows
        data.drop_duplicates(inplace=True)

        # ignore empty queries, empty labels or queries with the label "empty" or "too_short"
        data.dropna(subset=["query"], inplace=True)
        data.dropna(subset=["label"], inplace=True)
        data = data[~data["query"].astype(str).str.strip().eq("")]
        data = data[~data["label"].astype(str).str.strip().eq("")]
        data = data[~data["label"].astype(str).str.lower().isin({"empty", "too_short"})]

        return data

    def train_model(self, train_csv: Path, model_path: Path = MODEL_PATH):
        if not train_csv.exists():
            raise FileNotFoundError(f"Training file not found: {train_csv}")

        data = pd.read_csv(train_csv)
        print(f"Number of rows: {len(data)}")
        data = self.pre_clean_raw_data(data)
        print(f"Number of rows after pre-cleaning: {len(data)}")

        missing_columns = {"label", "query"} - set(data.columns)
        if missing_columns:
            raise ValueError(
                f"Training CSV must contain columns: {', '.join(sorted(missing_columns))}"
            )

        data = data[["label", "query"]].dropna(subset=["label"]).fillna({"query": ""})
        raw_queries = data["query"].astype(str).tolist()
        labels = data["label"].astype(str).values
        if len(labels) < 2:
            raise ValueError("Need at least two samples to train the classifier.")

        processed_queries = self.preprocess_queries(raw_queries)
        stratify = labels if len(np.unique(labels)) > 1 else None
        train_queries, test_queries, train_labels, test_labels = train_test_split(
            processed_queries,
            labels,
            test_size=0.2,
            random_state=42,
            stratify=stratify,
        )
        vectorizer = self.build_vectorizer()
        X, word_stats = self.build_feature_matrix(
            train_queries,
            vectorizer=vectorizer,
            word_stats=None,
            fit_vectorizer=True,
        )
        classifier = LogisticRegression(
            max_iter=1000,
            n_jobs=None,
            class_weight="balanced",
            solver="lbfgs",
            multi_class="auto",
        )
        classifier.fit(X, train_labels)
        X_test, _ = self.build_feature_matrix(
            test_queries,
            vectorizer=vectorizer,
            word_stats=word_stats,
            fit_vectorizer=False,
        )
        predictions = classifier.predict(X_test)
        report = classification_report(test_labels, predictions, zero_division=0)
        print("Test classification report (20% split):")
        print(report)
        payload = {
            "vectorizer": vectorizer,
            "classifier": classifier,
            "word_count_stats": word_stats,
        }
        joblib.dump(payload, model_path)
        print(
            f"Model trained on {len(train_labels)} samples (tested on {len(test_labels)}) "
            f"and saved to {model_path}"
        )


class QueryClassifier:
    """This classifies queries into predefined categories using rules and a simple ML model."""

    # leading non-word characters
    LEADING_JUNK_RE = re.compile(r"^[^\w]+")
    CONFIDENCE_THRESHOLD = 0.6

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
        """Placeholder for ML model classification.
        In a real implementation, this would call a trained model to classify the query.
        Here we just assign LEGAL_TERM for demonstration.
        """
        classifier = get_model_classifier()
        predictions = classifier.predict_queries([qclass.query_clean])
        if len(predictions) == 1:
            label, confidence = predictions[0]
            if confidence >= self.CONFIDENCE_THRESHOLD:
                qclass.label = QueryLabel(label)
                qclass.confidence = confidence


_model_classifier = None


def get_model_classifier() -> ModelQueryClassifier:
    global _model_classifier
    if _model_classifier is None:
        _model_classifier = ModelQueryClassifier()
        _model_classifier.load_model()
    return _model_classifier
