from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import ListView, TemplateView


class AuthedViewMixin(LoginRequiredMixin, PermissionRequiredMixin):
    """View mixin for views that require authentication and permissions (ie. most views)."""

    permission_required = []

    def get_permission_required(self):
        perms = super().get_permission_required()
        return list(perms)


class HomePageView(AuthedViewMixin, TemplateView):
    template_name = "peachjam/home.html"


class GenericListView(AuthedViewMixin, ListView):
    """
    A generic list view, with year and alphabetical title filters
    that can be incorporated into site wide list views."""

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        object_list = self.object_list
        context = self.get_context_data()
        context_object_name = self.get_context_object_name(self.object_list)
        alphabet = request.GET.get("alphabet")
        year = request.GET.get("year")
        author = request.GET.get("author")

        if author is not None:
            object_list = object_list.filter(authoring_body__name=author)

        if alphabet is not None:
            object_list = object_list.filter(title__istartswith=alphabet)

        if year is not None:
            object_list = object_list.filter(date__year=year)

        if alphabet is not None and year is not None and author is not None:
            object_list = object_list.filter(
                title__istartswith=alphabet,
                date__year=year,
                authoring_body__name=author,
            )

        context[context_object_name] = object_list
        return self.render_to_response(context)
