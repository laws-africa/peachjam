from functools import cached_property

from django.contrib.auth.mixins import LoginRequiredMixin
from guardian.shortcuts import get_objects_for_group
from rest_framework.generics import get_object_or_404

from peachjam.models import CoreDocument, DocumentAccessGroup
from peachjam.views import FilteredDocumentListView


class DocumentAccessGroupDetailView(LoginRequiredMixin, FilteredDocumentListView):
    template_name = "peachjam/document_access_group_detail.html"
    context_object_name = "documents"

    @cached_property
    def public_group(self):
        return get_object_or_404(DocumentAccessGroup, pk=self.kwargs.get("pk"))

    def get_perms(self):
        # get view permission for each subclass of CoreDocument
        return [
            f"{klass._meta.app_label}.view_{klass._meta.model_name}"
            for klass in CoreDocument.__subclasses__()
        ]

    def get_base_queryset(self, exclude=None):
        ids = []
        perms = self.get_perms()
        for p in perms:
            ids.extend(
                get_objects_for_group(self.public_group.group, p).values_list(
                    "id", flat=True
                )
            )

        qs = super().get_base_queryset(exclude=exclude).filter(id__in=ids)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["group"] = self.public_group
        return context
