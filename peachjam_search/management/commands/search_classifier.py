import sys
from pathlib import Path

import pandas as pd
from django.core.management.base import BaseCommand, CommandError

from peachjam_search.classifier import QueryClassifier
from peachjam_search.classifier.ml_classifier import MLQueryClassifier


class Command(BaseCommand):
    help = "Train the query classifier model or label queries in a CSV using the existing model."

    def add_arguments(self, parser):
        parser.add_argument(
            "csv_file",
            help="Path to the CSV file. For training it must contain 'query' and 'label'. "
            "For labelling it must contain a single column of queries.",
        )
        parser.add_argument(
            "--model-path",
            dest="model_path",
            default=None,
            help="Optional model path. Defaults to the packaged classifier path.",
        )
        parser.add_argument(
            "--label",
            action="store_true",
            help="If provided, label all queries in the CSV and write the results to stdout.",
        )

    def handle(self, *args, **options):
        csv_path = Path(options["csv_file"])
        if not csv_path.exists():
            raise CommandError(f"CSV file not found: {csv_path}")

        model_path_option = options.get("model_path")
        model_path = (
            Path(model_path_option)
            if model_path_option
            else MLQueryClassifier.MODEL_PATH
        )

        if options.get("label"):
            self.label_queries(csv_path)
        else:
            model_path.parent.mkdir(parents=True, exist_ok=True)
            self.train_classifier(csv_path, model_path)

    def train_classifier(self, csv_path: Path, model_path: Path):
        classifier = MLQueryClassifier()
        try:
            classifier.train_model(csv_path, model_path=model_path)
        except (FileNotFoundError, ValueError) as exc:
            raise CommandError(str(exc))

    def label_queries(self, csv_path: Path):
        try:
            data = pd.read_csv(csv_path)
        except Exception as exc:  # pragma: no cover
            raise CommandError(f"Could not read CSV: {exc}")

        if data.empty:
            raise CommandError("Input CSV has no rows to label.")

        if len(data.columns) != 1:
            raise CommandError(
                "Labelling requires a single-column CSV containing the queries."
            )

        query_column = data.columns[0]
        queries = data[query_column].fillna("").astype(str).tolist()

        classifier = QueryClassifier()
        labels = []
        confidences = []
        for query in queries:
            qclass = classifier.classify(query)
            labels.append(qclass.label.value if qclass.label else "")
            confidences.append(
                qclass.confidence if qclass.confidence is not None else 0.0
            )

        output_df = pd.DataFrame(
            {"query": queries, "label": labels, "label_confidence": confidences}
        )
        output_df.to_csv(sys.stdout, index=False)
