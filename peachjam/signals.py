from django.db.models import signals
from django.dispatch import receiver

from peachjam.models import CoreDocument, ExtractedCitation, SourceFile, Work
from peachjam.tasks import update_extracted_citations_for_a_work


@receiver(signals.post_save)
def doc_saved_update_language(sender, instance, **kwargs):
    """Update language list on related work when a subclass of CoreDocument is saved."""
    if isinstance(instance, CoreDocument) and not kwargs["raw"]:
        instance.work.update_languages()


@receiver(signals.post_delete)
def doc_deleted_update_language(sender, instance, **kwargs):
    """Update language list on related work after a subclass of CoreDocument is deleted."""
    if isinstance(instance, CoreDocument):
        # get by foreign key, because the actual instance in the db is now gone
        work = Work.objects.filter(pk=instance.work_id).first()
        if work:
            work.update_languages()


@receiver(signals.post_save)
def doc_saved_update_extracted_citations(sender, instance, **kwargs):
    """Update extracted citations when a subclass of CoreDocument is saved."""
    if isinstance(instance, CoreDocument) and not kwargs["raw"]:
        update_extracted_citations_for_a_work(instance.work_id)


@receiver(signals.post_delete)
def doc_deleted_update_extracted_citations(sender, instance, **kwargs):
    """Update language list on related work after a subclass of CoreDocument is deleted."""
    if isinstance(instance, CoreDocument):
        update_extracted_citations_for_a_work(instance.work_id)


@receiver(signals.post_save, sender=SourceFile)
def convert_to_pdf(sender, instance, created, **kwargs):
    """Convert a source file to PDF when it's saved"""
    if created:
        instance.ensure_file_as_pdf()


@receiver(signals.post_save, sender=ExtractedCitation)
def extracted_citation_saved(sender, instance, **kwargs):
    """Update citation counts on works."""
    ExtractedCitation.update_counts_for_work(instance.citing_work)
    ExtractedCitation.update_counts_for_work(instance.target_work)


@receiver(signals.post_delete, sender=ExtractedCitation)
def extracted_citation_deleted(sender, instance, **kwargs):
    """Update citation counts on works."""
    ExtractedCitation.update_counts_for_work(instance.citing_work)
    ExtractedCitation.update_counts_for_work(instance.target_work)
