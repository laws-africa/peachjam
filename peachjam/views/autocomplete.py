from dal import autocomplete
from django.db.models import Q

from peachjam.models import Judgment, Work


class WorkAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_staff:
            return Work.objects.none()

        qs = Work.objects.all()
        if self.q:
            qs = qs.filter(Q(title__icontains=self.q) | Q(frbr_uri__icontains=self.q))

        return qs


class JudgmentAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_staff:
            return Judgment.objects.none()

        qs = Judgment.objects.all()
        if self.q:
            qs = qs.filter(title__istartswith=self.q)

        return qs
