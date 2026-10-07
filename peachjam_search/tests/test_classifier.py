from unittest import TestCase
from unittest.mock import Mock

from peachjam_search.classifier import QueryClassifier


class ClassifierTest(TestCase):
    def setUp(self):
        self.cls = QueryClassifier()

    def test_classifier_simple(self):
        self.assertTrue(self.cls.classify("").label.name, "EMPTY")
        self.assertTrue(self.cls.classify("  * ").label.name, "EMPTY")
        self.assertTrue(self.cls.classify("w").label.name, "TOO_SHORT")
        self.assertTrue(self.cls.classify("2").label.name, "NUMBERS")
        self.assertTrue(self.cls.classify("22").label.name, "NUMBERS")
        self.assertTrue(self.cls.classify("22 22").label.name, "NUMBERS")
        self.assertTrue(self.cls.classify("2022-02-02").label.name, "NUMBERS")

    def test_classifier_uses_ml_for_meaningful_one_word_queries(self):
        model = Mock()
        model.predict_queries.return_value = [("legal_term", 0.9)]

        qclass = QueryClassifier(ml_classifier=model).classify("appeal")

        self.assertEqual(qclass.label.value, "legal_term")
        self.assertEqual(qclass.confidence, 0.9)
        model.predict_queries.assert_called_once_with(["appeal"])

    def test_classifier_falls_back_to_too_short_for_uncertain_one_word_queries(self):
        model = Mock()
        model.predict_queries.return_value = [("legal_term", 0.6)]

        qclass = QueryClassifier(ml_classifier=model).classify("unfamiliar")

        self.assertEqual(qclass.label.value, "too_short")
        self.assertEqual(qclass.confidence, 1.0)

    def test_classifier_has_default_label_for_constitution(self):
        model = Mock()

        qclass = QueryClassifier(ml_classifier=model).classify(" Constitution ")

        self.assertEqual(qclass.label.value, "act_name")
        self.assertEqual(qclass.confidence, 1.0)
        model.predict_queries.assert_not_called()

    def test_classifier_has_default_label_for_known_legal_term(self):
        model = Mock()

        qclass = QueryClassifier(ml_classifier=model).classify("Rule 19")

        self.assertEqual(qclass.label.value, "legal_term")
        self.assertEqual(qclass.confidence, 1.0)
        model.predict_queries.assert_not_called()

    def test_classifier_treats_one_and_two_letter_queries_as_too_short(self):
        model = Mock()

        qclass = QueryClassifier(ml_classifier=model).classify("AI")

        self.assertEqual(qclass.label.value, "too_short")
        self.assertEqual(qclass.confidence, 1.0)
        model.predict_queries.assert_not_called()

    def test_classifier_recognises_case_name_separator(self):
        model = Mock()

        qclass = QueryClassifier(ml_classifier=model).classify("Donoghue v Stevenson")

        self.assertEqual(qclass.label.value, "case_name")
        self.assertEqual(qclass.confidence, 1.0)
        model.predict_queries.assert_not_called()
