from django.contrib import messages
from django.views.generic import FormView
from rest_framework.reverse import reverse_lazy

from peachjam.forms import ContactUsForm


class AboutPageView(FormView):
    form_class = ContactUsForm
    template_name = "peachjam/about.html"
    navbar_link = "about"
    success_url = reverse_lazy("about")

    def form_valid(self, form):
        form.send_email()
        messages.success(self.request, "Your message has been sent. Thank you!")
        return super().form_valid(form)
