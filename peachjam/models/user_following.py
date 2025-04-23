import logging

from countries_plus.models import Country
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.translation import override
from templated_email import send_templated_mail

from . import Author, CoreDocument, Court, CourtClass, CourtRegistry, Locality, Taxonomy

log = logging.getLogger(__name__)


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
    taxonomy = models.ForeignKey(
        Taxonomy,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="followers",
        verbose_name=_("taxonomy"),
    )
    last_alerted_at = models.DateTimeField(
        _("last alerted at"), null=True, blank=True, auto_now_add=True
    )

    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    # fields that can be followed
    follow_fields = (
        "court author court_class court_registry country locality taxonomy".split()
    )

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
                fields=["user", "taxonomy"],
                condition=models.Q(taxonomy__isnull=False),
                name="unique_user_taxonomy",
            ),
        ]

    def __str__(self):
        return f"{self.user} follows {self.followed_object}"

    @property
    def followed_field(self):
        for field in self.follow_fields:
            if getattr(self, field):
                return field

    @property
    def followed_object(self):
        field = self.followed_field
        if field:
            return getattr(self, field)

    def clean(self):
        super().clean()

        # Count how many fields are set (not None)
        set_fields = sum(
            1 for field in self.follow_fields if getattr(self, field) is not None
        )

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
        qs = CoreDocument.objects.preferred_language(
            self.user.userprofile.preferred_language.iso_639_3
        )
        if self.last_alerted_at:
            qs = qs.filter(created_at__gt=self.last_alerted_at)
        if self.court:
            qs = qs.filter(judgment__court=self.court)[:10]
            return {
                "followed_object": self.court,
                "documents": qs,
            }

        elif self.author:
            qs = qs.filter(genericdocument__author=self.author)[:10]
            return {
                "followed_object": self.author,
                "documents": qs,
            }
        elif self.court_class:
            qs = qs.filter(judgment__court__court_class=self.court_class)[:10]
            return {
                "followed_object": self.court_class,
                "documents": qs,
            }
        elif self.court_registry:
            qs = qs.filter(judgment__registry=self.court_registry)[:10]
            return {
                "followed_object": self.court_registry,
                "documents": qs,
            }
        elif self.country:
            qs = qs.filter(jurisdiction=self.country)[:10]
            return {
                "followed_object": self.country,
                "documents": qs,
            }
        elif self.locality:
            qs = qs.filter(locality=self.locality)[:10]
            return {
                "followed_object": self.locality,
                "documents": qs,
            }
        elif self.taxonomy:
            topics = [self.taxonomy] + [t for t in self.taxonomy.get_descendants()]
            qs = qs.filter(taxonomies__topic__in=topics)[:10]
            return {
                "followed_object": self.taxonomy,
                "documents": qs,
            }

    @classmethod
    def update_and_alert(cls, user):
        follows = UserFollowing.objects.filter(user=user)
        log.info(f"Found {follows.count()} follows for user {user.pk}")
        documents = []
        for follow in follows:
            new = follow.get_new_followed_documents()
            if new["documents"]:
                log.info(
                    f"Found {new['documents'].count()} new documents for {new['followed_object']}"
                )
                follow.last_alerted_at = timezone.now()
                follow.save()
                documents.append(new)
        if documents:
            log.info(f"Sending alert to user {user.pk}")
            cls.send_alert(user, documents)

    @classmethod
    def send_alert(cls, user, followed_documents):
        context = {
            "followed_documents": followed_documents,
            "user": user,
        }
        with override(user.userprofile.preferred_language.pk):
            send_templated_mail(
                template_name="user_following_alert.email",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                context=context,
            )
