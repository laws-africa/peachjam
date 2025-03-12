from countries_plus.models import Country
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
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
        qs = CoreDocument.objects.filter(created_at__gt=self.last_alerted_at)
        if self.court:
            qs.filter(judgment__court=self.court)
        elif self.author:
            qs.filter(genericdocument__author=self.author)
        elif self.court_class:
            qs.filter(judgment__court__court_class=self.court_class)
        elif self.court_registry:
            qs.filter(judgment__court__court_registry=self.court_registry)
        elif self.country:
            qs.filter(jurisdiction=self.country)
        elif self.locality:
            qs.filter(locality=self.locality)
        elif self.taxonomy_topic:
            topics = [self.taxonomy_topic] + [
                t for t in self.taxonomy_topic.get_descendants()
            ]
            qs.filter(taxonomies__topic__in=topics)
        return qs[:10]
