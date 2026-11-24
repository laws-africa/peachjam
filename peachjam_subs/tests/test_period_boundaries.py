from datetime import date

from django.test import SimpleTestCase


class PeriodBoundaryTest(SimpleTestCase):
    def test_anniversary_periods_are_contiguous_and_contain_every_date(self):
        from datetime import timedelta

        from peachjam_subs.dates import period_bounds

        for anchor, period, days in [
            (date(2028, 2, 29), "annually", 366 * 9),
            (date(2027, 1, 29), "monthly", 366 * 2),
            (date(2027, 1, 30), "monthly", 366 * 2),
            (date(2027, 1, 31), "monthly", 366 * 2),
        ]:
            previous_end = None
            for offset in range(days):
                value = anchor + timedelta(days=offset)
                start, end = period_bounds(anchor, value, period)
                self.assertLessEqual(start, value)
                self.assertGreaterEqual(end, value)
                if previous_end is not None and value > previous_end:
                    self.assertEqual(previous_end + timedelta(days=1), start)
                previous_end = end
