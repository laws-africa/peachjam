from django.shortcuts import get_object_or_404
from django.views.generic.base import TemplateView

from peachjam.models import Taxonomy


class ParalegalsView(TemplateView):
    template_name = "zambialii/paralegals.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["taxonomy"] = get_object_or_404(Taxonomy.objects, slug="paralegals")
        context["videos"] = [
            {
                "title": "Accessing the Paralegal Hub & Exploring the Training Manuals",
                "embed_url": "https://www.youtube.com/embed/eiKB3oaQDpA",
            },
            {
                "title": "Navigating Legal Information on the Paralegal Hub",
                "embed_url": "https://www.youtube.com/embed/l9GxanzOk4o",
            },
            {
                "title": "Researching When You Are Offline",
                "embed_url": "https://www.youtube.com/embed/bRQCXmclXPs",
            },
            {
                "title": "Exploring the Paralegal Training Manual",
                "embed_url": "https://www.youtube.com/embed/PZiIT3206rI",
            },
        ]

        return context
