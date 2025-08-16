from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.translation import override
from templated_email import send_templated_mail


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

    @classmethod
    def send_email_alerts(cls):
        """
        Sends email alerts to the user following the documents if they haven't been notified yet.
        """
        for event in cls.objects.filter(user_notified=False):
            # Check if the user has any subject documents

            event.send_email_alert()

    def send_email_alert(self):

        context = {
            "followed_documents": self.subject_documents.all(),
            "user": self.user_following.user,
            "manage_url_path": reverse("user_following_list"),
        }
        with override(self.user_following.user.userprofile.preferred_language.pk):
            send_templated_mail(
                template_name="user_following_alert",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[self.user_following.user.email],
                context=context,
            )

        self.user_notified = True
        self.save(update_fields=["user_notified"])
