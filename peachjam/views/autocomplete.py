from dal import autocomplete

from peachjam.models import Work


class WorkAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_staff:
            return Work.objects.none()

        qs = Work.objects.all()
        if self.q:
            qs = qs.filter(title__istartswith=self.q)

        return qs
