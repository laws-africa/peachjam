from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView


@method_decorator(staff_member_required, name="dispatch")
class FlynoteManagerView(TemplateView):
    template_name = "peachjam/flynote/manager.html"
