from countries_plus.models import Country
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import models
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _

from . import Author, CoreDocument, Court, CourtClass, CourtRegistry, Locality, Taxonomy


class UserFollowing(models.Model):
    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="following",
        verbose_name=_("user"),
    )
    court = models.ForeignKey(
        Court,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="followers",
        verbose_name=_("court"),
    )
    author = models.ForeignKey(
        Author,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="followers",
        verbose_name=_("author"),
    )
    court_class = models.ForeignKey(
        CourtClass,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="followers",
        verbose_name=_("court class"),
    )
    court_registry = models.ForeignKey(
        CourtRegistry,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="followers",
        verbose_name=_("court registry"),
    )
    country = models.ForeignKey(
        Country,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="followers",
        verbose_name=_("country"),
    )
    locality = models.ForeignKey(
        Locality,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="followers",
        verbose_name=_("locality"),
    )
    taxonomy_topic = models.ForeignKey(
        Taxonomy,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="followers",
        verbose_name=_("taxonomy topic"),
    )
    last_alerted_at = models.DateTimeField(_("last alerted at"), null=True, blank=True)

    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "court"],
                condition=models.Q(court__isnull=False),
                name="unique_user_court",
            ),
            models.UniqueConstraint(
                fields=["user", "author"],
                condition=models.Q(author__isnull=False),
                name="unique_user_author",
            ),
            models.UniqueConstraint(
                fields=["user", "court_class"],
                condition=models.Q(court_class__isnull=False),
                name="unique_user_court_class",
            ),
            models.UniqueConstraint(
                fields=["user", "court_registry"],
                condition=models.Q(court_registry__isnull=False),
                name="unique_user_court_registry",
            ),
            models.UniqueConstraint(
                fields=["user", "country"],
                condition=models.Q(country__isnull=False),
                name="unique_user_country",
            ),
            models.UniqueConstraint(
                fields=["user", "locality"],
                condition=models.Q(locality__isnull=False),
                name="unique_user_locality",
            ),
            models.UniqueConstraint(
                fields=["user", "taxonomy_topic"],
                condition=models.Q(taxonomy_topic__isnull=False),
                name="unique_user_taxonomy_topic",
            ),
        ]

    def __str__(self):
        return f"{self.user} follows {self.followed_object}"

    @property
    def followed_object(self):
        return (
            self.court
            or self.author
            or self.court_class
            or self.court_registry
            or self.country
            or self.locality
            or self.taxonomy_topic
        )

    def clean(self):
        super().clean()
        follow_fields = [
            self.court,
            self.author,
            self.court_class,
            self.court_registry,
            self.country,
            self.locality,
            self.taxonomy_topic,
        ]

        # Count how many fields are set (not None)
        set_fields = sum(1 for field in follow_fields if field is not None)

        if set_fields == 0:
            raise ValidationError(
                "One of the following fields must be set: court, author, court class, court registry, country, "
                "locality, taxonomy topic"
            )

        if set_fields > 1:
            raise ValidationError(
                "Only one of the following fields can be set: court, author, court class, court registry,"
                " country, locality, taxonomy topic"
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def get_new_followed_documents(self):
        qs = CoreDocument.objects.all()
        if self.last_alerted_at:
            qs.filter(created_at__gt=self.last_alerted_at)
        if self.court:
            return {
                "followed_object": self.court,
                "documents": qs.filter(judgment__court=self.court)[:10],
            }
        elif self.author:
            return {
                "followed_object": self.author,
                "documents": qs.filter(genericdocument__author=self.author)[:10],
            }
        elif self.court_class:
            return {
                "followed_object": self.court_class,
                "documents": qs.filter(judgment__court__court_class=self.court_class),
            }
        elif self.court_registry:
            return {
                "followed_object": self.court_registry,
                "documents": qs.filter(
                    judgment__court__court_registry=self.court_registry
                )[:10],
            }
        elif self.country:
            return {
                "followed_object": self.country,
                "documents": qs.filter(jurisdiction=self.country),
            }
        elif self.locality:
            return {
                "followed_object": self.locality,
                "documents": qs.filter(locality=self.locality),
            }
        elif self.taxonomy_topic:
            topics = [self.taxonomy_topic] + [
                t for t in self.taxonomy_topic.get_descendants()
            ]
            return {
                "followed_object": self.taxonomy_topic,
                "documents": qs.filter(taxonomies__topic__in=topics),
            }

    @classmethod
    def update_and_alert(cls):
        users = get_user_model().objects.filter(following__isnull=False).distinct()
        for user in users:
            follows = UserFollowing.objects.filter(user=user)
            documents = []
            for follow in follows:
                new = follow.get_new_followed_documents()
                if new["documents"]:
                    documents.append(follow.get_new_followed_documents())
            if documents:
                # TODO: we need a better way to do this, as we are updating the last_alerted_at for all follows
                # follows.update(last_alerted_at=timezone.now())
                cls.send_alert(user, documents)

    @classmethod
    def send_alert(cls, user, documents):
        documents = documents
        context = {
            "followed_documents": documents,
            "user": user,
            "site": Site.objects.get_current(),
        }
        html = render_to_string(
            "peachjam/emails/user_following_alert_email.html", context
        )
        plain_txt = render_to_string(
            "peachjam/emails/user_following_alert_email.txt", context
        )
        subject = settings.EMAIL_SUBJECT_PREFIX + _("New documents have been published")
        send_mail(
            subject=subject,
            message=plain_txt,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
            html_message=html,
        )
