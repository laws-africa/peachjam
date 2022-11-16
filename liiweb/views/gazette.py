from django.views.generic import TemplateView

from peachjam.models import Gazette


class GazetteListView(TemplateView):
    model = Gazette
    template_name = "liiweb/gazette_list.html"


class YearView(TemplateView):
    model = Gazette
    template_name = "liiweb/year.html"
