from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView
from rest_framework.reverse import reverse_lazy

from peachjam.forms import ContactUsForm


class AboutPageView(FormView):
    form_class = ContactUsForm
    template_name = "peachjam/about.html"
    navbar_link = "about"
    success_url = reverse_lazy("about")

    def get_form_kwargs(self, *args, **kwargs):
        # pre-fill the form with the user's email address if they are logged in
        kwargs = super().get_form_kwargs()
        if self.request.user.is_authenticated:
            kwargs["initial"] = {
                "email": self.request.user.email,
                "name": self.request.user.get_full_name(),
            }

        return kwargs

    def form_valid(self, form):
        form.send_email()
        messages.success(self.request, _("Your message has been sent. Thank you!"))
        return super().form_valid(form)
