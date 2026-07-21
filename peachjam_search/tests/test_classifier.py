from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from django.core.management import call_command

from peachjam_search.classifier import QueryClassifier


class ClassifierTest(TestCase):
    def setUp(self):
        self.cls = QueryClassifier()

    def test_classifier_simple(self):
        self.assertTrue(self.cls.classify("").label.name, "EMPTY")
        self.assertTrue(self.cls.classify("  * ").label.name, "EMPTY")
        self.assertTrue(self.cls.classify("word").label.name, "TOO_SHORT")
        self.assertTrue(self.cls.classify("w").label.name, "TOO_SHORT")
        self.assertTrue(self.cls.classify("2").label.name, "NUMBERS")
        self.assertTrue(self.cls.classify("22").label.name, "NUMBERS")
        self.assertTrue(self.cls.classify("22 22").label.name, "NUMBERS")
        self.assertTrue(self.cls.classify("2022-02-02").label.name, "NUMBERS")


class SearchClassifierCommandTest(TestCase):
    @patch(
        "peachjam_search.management.commands.search_classifier.MLQueryClassifier.predict_queries",
        return_value=[("case_name", 0.8)],
    )
    @patch(
        "peachjam_search.management.commands.search_classifier.MLQueryClassifier.load_model"
    )
    def test_evaluate_uses_rules_and_writes_per_query_results(
        self, load_model, predict_queries
    ):
        with TemporaryDirectory() as directory:
            directory = Path(directory)
            input_path = directory / "labelled-searches.csv"
            output_path = directory / "results.csv"
            input_path.write_text(
                "query,label\n22,numbers\n,empty\nsome legal words,act_name\n"
            )
            stdout = StringIO()

            call_command(
                "search_classifier",
                input_path,
                "--evaluate",
                "--model-path",
                directory / "candidate.joblib",
                "--evaluation-output",
                output_path,
                stdout=stdout,
            )

            self.assertIn("Accuracy: 0.667", stdout.getvalue())
            self.assertIn("Coverage: 1.000", stdout.getvalue())
            self.assertIn("Incorrect classifications: 1", stdout.getvalue())
            self.assertEqual(
                load_model.call_args.args[0], directory / "candidate.joblib"
            )
            predict_queries.assert_called_once_with(["some legal words"])
            self.assertEqual(
                output_path.read_text(),
                "query,expected_label,predicted_label,label_confidence,correct\n"
                "22,numbers,numbers,1.0,True\n"
                ",empty,empty,1.0,True\n"
                "some legal words,act_name,case_name,0.8,False\n",
            )
