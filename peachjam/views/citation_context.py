from functools import cached_property

from django.db.models import Prefetch, Q
from django.http import Http404
from django.utils.decorators import method_decorator

from peachjam.helpers import add_slash_to_frbr_uri
from peachjam.models import CoreDocument, ExtractedCitationContext
from peachjam.views import FilteredDocumentListView


@method_decorator(add_slash_to_frbr_uri(), name="setup")
class DocumentCitationContextView(FilteredDocumentListView):
    template_name = "peachjam/citation_context/_citation_context.html"

    @cached_property
    def document(self):
        obj = CoreDocument.objects.filter(
            expression_frbr_uri=self.kwargs.get("frbr_uri")
        ).first()
        if not obj:
            raise Http404()

        # TODO: extract perms logic into a mixin
        if obj.restricted:
            perm = f"{obj._meta.app_label}.view_{obj._meta.model_name}"
            if not self.request.user.has_perm(perm, obj):
                raise Http404()
        return obj

    @cached_property
    def citation_contexts(self):
        provision = self.kwargs.get("provision", "")
        q = Q(target_work=self.document.work)
        if provision:
            q &= Q(target_provision_eid__icontains=provision)
        contexts = ExtractedCitationContext.objects.filter(q)
        return contexts

    def get_base_queryset(self, *args, **kwargs):
        document_ids = self.citation_contexts.values_list("document_id", flat=True)
        prefetch = Prefetch(
            "citation_contexts",
            queryset=self.citation_contexts,
            to_attr="relevant_citation_contexts",
        )
        qs = CoreDocument.objects.filter(pk__in=document_ids).prefetch_related(prefetch)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["document"] = self.document
        if self.kwargs.get("provision"):
            context["provision"] = context["document"].friendly_provision_title(
                self.kwargs.get("provision")
            )

        return context
