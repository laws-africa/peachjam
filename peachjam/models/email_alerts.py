from django.db import models
from django.utils.translation import gettext_lazy as _


class EmailAlertFrequency(models.TextChoices):
    DAILY = "daily", _("Daily")
    WEEKLY = "weekly", _("Weekly")
    MONTHLY = "monthly", _("Monthly")
    NONE = "none", _("No email updates")
