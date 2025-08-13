from django.db import models


class TimelineEvent(models.Model):

    EVENT_TYPES = (("new_documents", "New Documents"),)

    user_following = models.ForeignKey(
        "peachjam.UserFollowing",
        on_delete=models.CASCADE,
        related_name="timeline_events",
    )
    subject_documents = models.ManyToManyField(
        "peachjam.CoreDocument", related_name="+"
    )
    event_type = models.CharField(
        max_length=256,
        choices=EVENT_TYPES,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    user_notified = models.BooleanField(default=False)
