def modify_document_detail_context(sender, context, view, **kwargs):
    if not context["show_related_documents"]:
        if (
            not view.request.user.is_authenticated
            or view.request.user.has_perm("peachjam_ml.view_documentembedding")
        ) and hasattr(context["document"], "embedding"):
            context["show_related_documents"] = True
