from datetime import date, datetime
from datetime import timezone as datetime_timezone
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from peachjam_subs.dates import period_bounds, site_date


class BillingDatesTest(SimpleTestCase):
    @override_settings(TIME_ZONE="Africa/Johannesburg")
    def test_site_midnight_does_not_depend_on_request_timezone_or_representation(self):
        local = datetime(2026, 10, 1, tzinfo=ZoneInfo("Africa/Johannesburg"))
        with timezone.override("America/Toronto"):
            self.assertEqual(date(2026, 10, 1), site_date(local))
            self.assertEqual(
                date(2026, 10, 1), site_date(local.astimezone(datetime_timezone.utc))
            )

    def test_periods_preserve_month_end_anniversaries(self):
        anchor = date(2026, 1, 31)
        self.assertEqual(
            (date(2026, 2, 28), date(2026, 3, 27)),
            period_bounds(anchor, date(2026, 2, 28), "monthly"),
        )
        self.assertEqual(
            (date(2026, 3, 31), date(2026, 4, 29)),
            period_bounds(anchor, date(2026, 3, 31), "monthly"),
        )

    def test_leap_year_and_dates_before_activation(self):
        anchor = date(2024, 2, 29)
        self.assertEqual(
            (date(2025, 2, 28), date(2026, 2, 27)),
            period_bounds(anchor, date(2025, 2, 28), "annually"),
        )
        self.assertEqual(
            (anchor, date(2025, 2, 27)),
            period_bounds(anchor, date(2024, 2, 1), "annually"),
        )
