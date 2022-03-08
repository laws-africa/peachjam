from django.views.generic import TemplateView


class HomePageView(TemplateView):
    template_name = 'peach_jam/home.html'
