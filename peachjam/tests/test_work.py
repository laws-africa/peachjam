from django.test import TestCase

from peachjam.models import Work


class WorkTestCase(TestCase):
    def test_explode_frbr_uri(self):
        work = Work.objects.create(title="Test Work", frbr_uri="/akn/za/act/2014/1")
        work.save()
        self.assertEqual("za", work.frbr_uri_country)
        self.assertIsNone(work.frbr_uri_locality)
        self.assertEqual("za", work.frbr_uri_place)
        self.assertEqual("act", work.frbr_uri_doctype)
        self.assertIsNone(work.frbr_uri_subtype)
        self.assertIsNone(work.frbr_uri_actor)
        self.assertEqual("2014", work.frbr_uri_date)
        self.assertEqual("1", work.frbr_uri_number)

        work = Work.objects.create(
            title="Test Work", frbr_uri="/akn/za-cpt/act/by-law/actor/2014/1"
        )
        work.save()
        self.assertEqual("za", work.frbr_uri_country)
        self.assertEqual("cpt", work.frbr_uri_locality)
        self.assertEqual("za-cpt", work.frbr_uri_place)
        self.assertEqual("act", work.frbr_uri_doctype)
        self.assertEqual("by-law", work.frbr_uri_subtype)
        self.assertEqual("actor", work.frbr_uri_actor)
        self.assertEqual("2014", work.frbr_uri_date)
        self.assertEqual("1", work.frbr_uri_number)
