from django.contrib import admin  # noqa

from africanlii.models import Court
from africanlii.models import Judgment
from africanlii.models import MatterType


admin.site.register(Judgment)
admin.site.register(MatterType)
admin.site.register(Court)
