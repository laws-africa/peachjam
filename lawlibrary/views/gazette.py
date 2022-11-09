from django.views.generic import TemplateView


class GazetteListView(TemplateView):
    template_name = "lawlibrary/gazette_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["name"] = "nick"
        return context


class YearView(TemplateView):
    template_name = "lawlibrary/year.html"
