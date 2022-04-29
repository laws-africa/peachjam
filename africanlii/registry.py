class DetailViewsRegistry:
    """View registry that maps doc_types to DetailView classes for documents
    using the register_doc_type() decorator.

    The views are stored as values where the key is the doc_type string.
    {
        'legislation': <class 'africanlii.views.legislation.LegislationDetailView'>
    }
    """

    views = {}

    def register_doc_type(self, doc_type):
        def wrapper(klass):
            self.views[doc_type] = klass
            return klass

        return wrapper


registry = DetailViewsRegistry()
