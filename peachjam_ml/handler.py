def modify_document_detail_context(sender, context, view, **kwargs):
    if not context["show_related_documents"]:
        if hasattr(context["document"], "embedding"):
            context["show_related_documents"] = True
