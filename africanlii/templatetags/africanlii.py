from django import template

from peachjam.models import Book

register = template.Library()


@register.simple_tag
def law_reader_options():
    law_readers = Book.objects.filter(
        taxonomies__topic__slug="law-readers-refugee-law-readers"
    )
    return list(law_readers.all())
