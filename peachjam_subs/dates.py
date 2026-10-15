"""Calendar dates used by subscriptions, independent of a request's timezone."""

from datetime import timedelta

from dateutil.relativedelta import relativedelta
from django.utils import timezone


def site_date(value=None):
    """Return an instant's calendar date in the configured site's timezone."""
    return timezone.localdate(value, timezone=timezone.get_default_timezone())


def period_bounds(anchor, value, period):
    """Return an anniversary-based period, without drifting at month ends."""
    value = max(value, anchor)
    months = 1 if period == "monthly" else 12
    elapsed = (value.year - anchor.year) * 12 + value.month - anchor.month
    count = elapsed // months
    start = anchor + relativedelta(months=count * months)
    if start > value:
        count -= 1
        start = anchor + relativedelta(months=count * months)
    end = start + relativedelta(months=months) - timedelta(days=1)
    return start, end
