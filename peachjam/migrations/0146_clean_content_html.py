# Generated by Django 3.2.25 on 2024-07-08 10:08
import re

from django.db import migrations
from django.db.models.functions import Length
from lxml.etree import ParserError

from peachjam.xmlutils import parse_html_str


def clean_content_html(content_html):
    """Ensure that content_html is not just whitespace HTML. Returns the cleaned value."""
    if not content_html:
        return None

    # return None if the HTML doesn't have any content
    try:
        root = parse_html_str(content_html)
        text = "".join(root.itertext()).strip()
        text = re.sub(r"\s", "", text)
        if not text:
            return None
    except (ValueError, ParserError):
        return None

    return content_html


def forwards(apps, schema_editor):
    CoreDocument = apps.get_model("peachjam", "CoreDocument")
    # get docs where the length of content_html is > 0 but less than 500
    qs = CoreDocument.objects.annotate(text_length=Length("content_html")).filter(
        content_html_is_akn=False,
        content_html__isnull=False,
        text_length__gt=0,
        text_length__lt=1000,
    )
    for doc in qs.iterator(100):
        html = doc.content_html
        doc.content_html = clean_content_html(doc.content_html)
        if doc.content_html != html:
            doc.save(update_fields=["content_html"])


class Migration(migrations.Migration):

    dependencies = [
        ("peachjam", "0145_alter_courtregistry_options"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
