from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import TemplateView


class AuthedViewMixin(LoginRequiredMixin, PermissionRequiredMixin):
    """ View mixin for views that require authentication and permissions (ie. most views).
    """
    permission_required = []

    def get_permission_required(self):
        perms = super().get_permission_required()
        return list(perms)


class FindDocumentsView(AuthedViewMixin, TemplateView):
    template_name = 'peachjam/find_documents.html'
