import re
from datetime import datetime

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

# TODO: get these from cobalt
FRBR_URI_DOCTYPES = ["act", "bill", "doc", "judgment", "statement", "officialGazette"]
FRBR_URI_DOCTYPE_CHOICES = ((x, x) for x in FRBR_URI_DOCTYPES)

validate_frbr_uri_component = RegexValidator(
    r"^[a-z0-9_-]+$", "Only lowercase letters, numbers, _ and - allowed"
)


def validate_frbr_uri_date(value):
    # yyyy
    if re.match(r"\d{4}$", value):
        try:
            datetime.strptime(value, "%Y")
            return
        except ValueError as e:
            raise ValidationError(e)

    # yyyy-mm
    if re.match(r"\d{4}-\d{2}$", value):
        try:
            datetime.strptime(value, "%Y-%m")
            return
        except ValueError as e:
            raise ValidationError(e)

    # yyyy-mm-dd
    if re.match(r"\d{4}-\d{2}-\d{2}$", value):
        try:
            datetime.strptime(value, "%Y-%m-%d")
            return
        except ValueError as e:
            raise ValidationError(e)
