from unittest import TestCase

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
