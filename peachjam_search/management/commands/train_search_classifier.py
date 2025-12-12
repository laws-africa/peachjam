from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from peachjam_search.classifier.ml_classifier import MLQueryClassifier


class Command(BaseCommand):
    help = "Train the query classifier model using labeled query CSV data."

    def add_arguments(self, parser):
        parser.add_argument(
            "csv_file",
            help="Path to the CSV file containing labeled queries.",
        )
        parser.add_argument(
            "--model-path",
            dest="model_path",
            default=None,
            help="Optional output path for the trained model. "
            "Defaults to the standard classifier path.",
        )

    def handle(self, *args, **options):
        csv_path = Path(options["csv_file"])
        model_path_option = options.get("model_path")
        model_path = (
            Path(model_path_option)
            if model_path_option
            else MLQueryClassifier.MODEL_PATH
        )

        if not csv_path.exists():
            raise CommandError(f"CSV file not found: {csv_path}")

        model_path.parent.mkdir(parents=True, exist_ok=True)

        classifier = MLQueryClassifier()
        try:
            classifier.train_model(csv_path, model_path=model_path)
        except (FileNotFoundError, ValueError) as exc:
            raise CommandError(str(exc))
