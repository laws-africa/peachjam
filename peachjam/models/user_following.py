import logging

from countries_plus.models import Country
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.urls.base import reverse
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

    def get_documents_queryset(self):
        qs = CoreDocument.objects

        if self.court:
            return qs.filter(judgment__court=self.court)

        if self.author:
            return qs.filter(genericdocument__author=self.author)

        if self.court_class:
            return qs.filter(judgment__court__court_class=self.court_class)

        if self.court_registry:
            return qs.filter(judgment__registry=self.court_registry)

        if self.country:
            return qs.filter(jurisdiction=self.country)

        if self.locality:
            return qs.filter(locality=self.locality)

        if self.taxonomy:
            topics = [self.taxonomy] + [t for t in self.taxonomy.get_descendants()]
            return qs.filter(taxonomies__topic__in=topics)

    def get_new_followed_documents(self):
        qs = self.get_documents_queryset().preferred_language(
            self.user.userprofile.preferred_language.iso_639_3
        )
        if self.last_alerted_at:
            qs = qs.filter(created_at__gt=self.last_alerted_at)

        return {
            "followed_object": self.followed_object,
            "documents": qs[:10],
        }

    @classmethod
    def update_and_alert(cls, user):
        follows = UserFollowing.objects.filter(user=user)
        log.info(f"Found {follows.count()} follows for user {user.pk}")
        followed_documents = []
        for follow in follows:
            new = follow.get_new_followed_documents()
            if new["documents"]:
                log.info(
                    f"Found {new['documents'].count()} new documents for {new['followed_object']}"
                )
                follow.last_alerted_at = timezone.now()
                follow.save()
                followed_documents.append(new)
        if followed_documents:
            log.info(f"Sending alert to user {user.pk}")
            cls.send_alert(user, followed_documents)

    @classmethod
    def send_alert(cls, user, followed_documents):
        context = {
            "followed_documents": followed_documents,
            "user": user,
            "manage_url_path": reverse("user_following_list"),
        }
        with override(user.userprofile.preferred_language.pk):
            send_templated_mail(
                template_name="user_following_alert",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                context=context,
            )
