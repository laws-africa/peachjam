from peachjam.models import Locality
from peachjam.views.home import HomePageView as BaseHomePageView


class HomePageView(BaseHomePageView):
    def get_context_data(self, **kwargs):
        localities = Locality.objects.filter(jurisdiction__pk="AA").exclude(code="au")
        return super().get_context_data(localities=localities)
