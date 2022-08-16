from django.views.generic import ListView

from peachjam.models import Legislation


class LegislationListView(ListView):
    model = Legislation
    template_name = "lawlibrary/legislation_list.html"
    context_object_name = "documents"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["national_legislation_list"] = self.model.objects.filter(
            locality__isnull=False
        )
        return context
