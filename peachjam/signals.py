import allauth.account.signals as allauth_signals
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.db.models import signals
from django.dispatch import receiver
from django.dispatch.dispatcher import Signal
from django_comments.models import Comment
from django_comments.signals import comment_will_be_posted

from peachjam.customerio import get_customerio
from peachjam.models import (
    Annotation,
    CoreDocument,
    DocumentContent,
    ExtractedCitation,
    SavedDocument,
    SourceFile,
    UserFollowing,
    UserProfile,
    Work,
)
from peachjam.tasks import (
    generate_judgment_summary,
    update_extracted_citations_for_a_work,
)
from peachjam_search.models import SavedSearch

User = get_user_model()


# a user has requested a password reset
password_reset_started = Signal()


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


@receiver(signals.post_save, sender=User)
def add_saved_document_permissions(sender, instance, created, **kwargs):
    if created:
        all_users_group, _ = Group.objects.get_or_create(name="AllUsers")
        instance.groups.add(all_users_group)


@receiver(comment_will_be_posted, sender=Comment)
def before_comment_posted(sender, comment, request, **kwargs):
    # prevent unauthorized comments
    if not comment.user or not comment.user.is_staff:
        return False


@receiver(user_logged_in)
def set_user_language(sender, request, user, **kwargs):
    setattr(request, "set_language", user.userprofile.preferred_language.iso_639_1)


###
# Analytics


@receiver(signals.post_save, sender=User)
def user_saved_updated_customerio(sender, instance, **kwargs):
    get_customerio().update_user_details(instance)


@receiver(allauth_signals.user_signed_up)
def user_signed_up_update_customerio(sender, request, user, **kwargs):
    get_customerio().track_user_signed_up(user)


@receiver(signals.post_save, sender=UserProfile)
def userprofile_saved_updated_customerio(sender, instance, **kwargs):
    get_customerio().update_user_details(instance.user)


@receiver(user_logged_in)
@receiver(allauth_signals.user_logged_in)
def user_logged_in_update_customerio(sender, request, user, **kwargs):
    get_customerio().track_user_logged_in(user)


# allauth uses the same signal
@receiver(user_logged_out)
def user_logged_out_update_customerio(sender, request, user, **kwargs):
    get_customerio().track_user_logged_out(user)


@receiver(signals.post_save, sender=SavedSearch)
def saved_search_customerio(sender, instance, created, raw, **kwargs):
    if not raw and created:
        get_customerio().track_saved_search(instance)


@receiver(signals.pre_delete, sender=SavedSearch)
def unsaved_search_customerio(sender, instance, **kwargs):
    get_customerio().track_unsaved_search(instance)


@receiver(signals.post_save, sender=SavedDocument)
def saved_document_customerio(sender, instance, created, raw, **kwargs):
    if not raw and created:
        get_customerio().track_saved_document(instance)


@receiver(signals.pre_delete, sender=SavedDocument)
def unsaved_document_customerio(sender, instance, **kwargs):
    get_customerio().track_unsaved_document(instance)


@receiver(signals.post_save, sender=UserFollowing)
def user_followed_customerio(sender, instance, created, raw, **kwargs):
    if not raw and created:
        get_customerio().track_follow(instance)


@receiver(signals.pre_delete, sender=UserFollowing)
def user_unfollowed_customerio(sender, instance, **kwargs):
    get_customerio().track_unfollow(instance)


@receiver(signals.post_save, sender=Annotation)
def annotated_customerio(sender, instance, created, raw, **kwargs):
    if not raw and created:
        get_customerio().track_annotated(instance)


@receiver(signals.pre_delete, sender=Annotation)
def unannotated_customerio(sender, instance, **kwargs):
    get_customerio().track_unannotated(instance)


@receiver(password_reset_started, sender=User)
def password_reset_started_customerio(sender, request, user, **kwargs):
    get_customerio().track_password_reset_started(user)


@receiver(allauth_signals.password_reset, sender=User)
def password_reset_customerio(sender, request, user, **kwargs):
    get_customerio().track_password_reset(user)


@receiver(signals.post_save, sender=DocumentContent)
def judgment_content_changed_generate_summary(sender, instance, **kwargs):
    if not instance.document.doc_type == "judgment":
        return
    judgment = instance.document
    should_generate = (
        not judgment.summary  # No summary at all
        or judgment.summary_ai_generated  # Summary exists but is AI-generated
    ) and (
        not judgment.must_be_anonymised or judgment.anonymised  # Anonymization OK
    )
    if should_generate:
        generate_judgment_summary(judgment.pk)
