import sys
from pathlib import Path

import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from sklearn.metrics import accuracy_score, classification_report

from peachjam_search.classifier import QueryClassifier
from peachjam_search.classifier.ml_classifier import MLQueryClassifier


class Command(BaseCommand):
    help = "Train, label, or evaluate the query classifier model using a CSV."

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
        modes = parser.add_mutually_exclusive_group()
        modes.add_argument(
            "--label",
            action="store_true",
            help="If provided, label all queries in the CSV and write the results to stdout.",
        )
        modes.add_argument(
            "--evaluate",
            action="store_true",
            help="Evaluate a model against a CSV containing 'query' and 'label' columns.",
        )
        parser.add_argument(
            "--evaluation-output",
            type=Path,
            help="Optional CSV path for per-query evaluation results.",
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

        if options.get("evaluation_output") and not options.get("evaluate"):
            raise CommandError("--evaluation-output can only be used with --evaluate.")

        if options.get("label"):
            self.label_queries(csv_path)
        elif options.get("evaluate"):
            self.evaluate_classifier(
                csv_path,
                model_path=model_path,
                output_path=options.get("evaluation_output"),
            )
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

    def evaluate_classifier(
        self, csv_path: Path, model_path: Path, output_path: Path | None = None
    ):
        """Evaluate the rule-first production classifier against labelled queries."""
        try:
            data = pd.read_csv(csv_path)
            data = MLQueryClassifier().normalise_labelled_data(data)
        except ValueError as exc:
            raise CommandError(str(exc))
        except Exception as exc:
            raise CommandError(f"Could not read evaluation CSV: {exc}")

        data = data.dropna(subset=["label"])
        data = data[data["label"].astype(str).str.strip().ne("")]
        data = data[["query", "label"]].fillna({"query": ""})
        if data.empty:
            raise CommandError("Evaluation CSV has no labelled queries.")

        ml_classifier = MLQueryClassifier()
        try:
            ml_classifier.load_model(model_path)
        except FileNotFoundError as exc:
            raise CommandError(str(exc))

        classifier = QueryClassifier(ml_classifier=ml_classifier)
        queries = data["query"].astype(str).tolist()
        expected_labels = data["label"].astype(str).tolist()
        classifications = classifier.classify_queries(queries)
        predicted_labels = [
            classification.label.value if classification.label else ""
            for classification in classifications
        ]
        confidences = [
            classification.confidence if classification.confidence is not None else 0.0
            for classification in classifications
        ]
        correct = [
            expected == predicted
            for expected, predicted in zip(expected_labels, predicted_labels)
        ]
        coverage = sum(bool(label) for label in predicted_labels) / len(
            predicted_labels
        )

        results = pd.DataFrame(
            {
                "query": queries,
                "expected_label": expected_labels,
                "predicted_label": predicted_labels,
                "label_confidence": confidences,
                "correct": correct,
            }
        )
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            results.to_csv(output_path, index=False)

        accuracy = accuracy_score(expected_labels, predicted_labels)
        report = classification_report(
            expected_labels,
            predicted_labels,
            zero_division=0,
            digits=3,
        )
        self.stdout.write(
            f"Evaluated {len(results)} labelled queries using {model_path}"
        )
        self.stdout.write(f"Accuracy: {accuracy:.3f}")
        self.stdout.write(f"Coverage: {coverage:.3f}")
        self.stdout.write("Classification report:")
        self.stdout.write(report)

        errors = results[~results["correct"]]
        self.stdout.write(f"Incorrect classifications: {len(errors)}")
        if output_path:
            self.stdout.write(f"Per-query results written to {output_path}")
        elif not errors.empty:
            self.stdout.write("First 20 incorrect classifications:")
            self.stdout.write(errors.head(20).to_string(index=False))
