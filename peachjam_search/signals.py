from django.db.models.signals import post_save
from django.dispatch import receiver

from peachjam.models import CoreDocument, SavedSearch, UserFollowing


@receiver(post_save)
def document_saved(sender, instance, **kwargs):
    if isinstance(instance, CoreDocument) and not kwargs["raw"]:
        # if there are multiple documents under this same work, and this is the most recent one,
        # then the previously most recent one may be invalid; pretend we've re-saved the other docs to
        # re-index them into elasticsearch.
        if instance.is_most_recent():
            # get all non-most-recent docs (ie. docs before this date)
            for doc in CoreDocument.objects.filter(
                work=instance.work, date__lt=instance.date
            ):
                post_save.send(doc.__class__, instance=doc, created=False, raw=False)


@receiver(post_save, sender=SavedSearch)
def create_user_following(sender, instance, created, **kwargs):
    if created:
        UserFollowing.objects.create(
            user=instance.user,
            saved_search=instance,
        )
