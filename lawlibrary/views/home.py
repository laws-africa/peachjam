from django.views.generic import TemplateView


class HomePageView(TemplateView):
    template_name = "lawlibrary/home.html"

    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        return self.render_to_response(context)
