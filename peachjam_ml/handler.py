def modify_document_detail_context(sender, context, view, **kwargs):
    if not context["show_related_documents"]:
        if view.request.user.has_perm("peachjam_ml.view_documentembedding") and hasattr(
            context["document"], "documentembedding"
        ):
            context["show_related_documents"] = True
