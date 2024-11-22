from django.http import Http404
from django.urls import reverse
from django.views.generic import RedirectView


class RedirectHomeView(RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        if not getattr(self.request, "microsite", None):
            raise Http404()

        return reverse(
            "locality_legislation_list",
            kwargs={"code": self.request.microsite["locality"].place_code()},
        )
