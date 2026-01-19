from django.core.management.base import BaseCommand
from django.utils.text import slugify

from peachjam.models import Journal, JournalArticle, VolumeIssue


class Command(BaseCommand):
    help = "Backfill missing slugs for journals and volume issues."

    def handle(self, *args, **options):
        journal_count = 0
        for journal in Journal.objects.all():
            slug = (journal.slug or "").strip().lower()
            if not slug or slug in {"none", "null"}:
                journal.slug = slugify(journal.title)
            original_slug = journal.slug
            journal.slug = journal.get_unique_slug(journal.slug)
            if journal.slug != original_slug:
                journal.save(update_fields=["slug"])
                journal_count += 1

        volume_count = 0
        for volume in VolumeIssue.objects.all():
            slug = (volume.slug or "").strip().lower()
            if not slug or slug in {"none", "null"}:
                volume.slug = slugify(volume.title)
            original_slug = volume.slug
            volume.slug = volume.get_unique_slug(volume.slug)
            if volume.slug != original_slug:
                volume.save(update_fields=["slug"])
                volume_count += 1

        article_count = 0
        for article in JournalArticle.objects.all():
            slug = (article.slug or "").strip().lower()
            if not slug or slug in {"none", "null"}:
                article.slug = slugify(article.title)
            original_slug = article.slug
            article.slug = article.get_unique_slug(article.slug)
            if article.slug != original_slug:
                article.save(update_fields=["slug"])
                article_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Backfilled {} journals, {} volume issues, and {} journal articles.".format(
                    journal_count, volume_count, article_count
                )
            )
        )
