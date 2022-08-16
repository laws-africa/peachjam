from django.views.generic import ListView

from peachjam.models import Legislation


class LegislationListView(ListView):
    model = Legislation
    template_name = "lawlibrary/legislation_list.html"
    context_object_name = "documents"
