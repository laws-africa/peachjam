from functools import cached_property

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView
from guardian.shortcuts import get_objects_for_group
from rest_framework.generics import get_object_or_404

from peachjam.models import PublicGroup
from peachjam.views import FilteredDocumentListView


class UserGroupListView(LoginRequiredMixin, ListView):
    template_name = "peachjam/user_groups.html"
    context_object_name = "groups"

    def get_queryset(self):
        return PublicGroup.objects.filter(group__in=self.request.user.groups.all())


class GroupDocumentListView(LoginRequiredMixin, FilteredDocumentListView):
    template_name = "peachjam/group_documents.html"
    context_object_name = "documents"

    @cached_property
    def public_group(self):
        return get_object_or_404(PublicGroup, slug=self.kwargs.get("slug"))

    def get_base_queryset(self, exclude=None):
        ids = []
        perms = [
            "peachjam.view_genericdocument",
            "peachjam.view_judgment",
            "peachjam.view_legislation",
        ]
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
