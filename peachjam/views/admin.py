from django.contrib.auth.mixins import LoginRequiredMixin
from django.http.response import HttpResponseForbidden
from django.views.generic.base import TemplateView

from peachjam.models import CoreDocument


class CheckDuplicateFilesView(LoginRequiredMixin, TemplateView):
    template_name = "admin/_check_duplicate_files.html"

    def get(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return HttpResponseForbidden("Forbidden")
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sha256 = self.request.GET.get("sha256")
        if sha256:
            context["duplicate_documents"] = list(
                CoreDocument.objects.filter(source_file__sha256=sha256).all()
            )
        return context
