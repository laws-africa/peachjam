from peachjam.models import Book, Journal
from peachjam.registry import registry
from peachjam.views.generic_views import (
    BaseDocumentDetailView,
    FilteredDocumentListView,
)


class BookListView(FilteredDocumentListView):
    queryset = Book.objects.all()
    model = Book
    template_name = "peachjam/book_list.html"
    navbar_link = "books"


@registry.register_doc_type("book")
class BookDetailView(BaseDocumentDetailView):
    model = Book
    template_name = "peachjam/book_detail.html"


class JournalListView(FilteredDocumentListView):
    queryset = Journal.objects.all()
    model = Journal
    template_name = "peachjam/journal_list.html"
    navbar_link = "journals"


@registry.register_doc_type("journal")
class JournalDetailView(BaseDocumentDetailView):
    model = Journal
    template_name = "peachjam/journal_detail.html"
