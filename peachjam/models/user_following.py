import heapq
import logging
from itertools import groupby

from countries_plus.models import Country
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.urls.base import reverse
from django.utils.translation import gettext_lazy as _
from django.utils.translation import override
from templated_email import send_templated_mail

from . import (
    Author,
    CoreDocument,
    Court,
    CourtClass,
    CourtRegistry,
    Locality,
    Taxonomy,
    TimelineEvent,
)

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
            # TODO: remove followed object
            "followed_object": self.followed_object,
            "documents": qs[:10],
        }

    @classmethod
    def update_and_alert(cls, user):
        follows = UserFollowing.objects.filter(user=user)
        log.info(f"Found {follows.count()} follows for user {user.pk}")
        for follow in follows:
            new = follow.get_new_followed_documents()
            if new["documents"]:
                log.info(
                    f"Found {new['documents'].count()} new documents for {new['followed_object']}"
                )

                # follow.last_alerted_at = timezone.now()
                # follow.save()

                # add to timeline
                timeline_event = TimelineEvent.objects.create(
                    user_following=follow,
                    event_type="new_documents",
                )
                timeline_event.subject_documents.set(new["documents"])

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


def get_user_following_timeline(user, docs_per_source, max_docs, before_date=None):
    # Get the latest documents from all followed sources
    def apply_filter(qs):
        if before_date:
            qs = qs.filter(created_at__lt=before_date)
        return qs

    sources = [
        (
            f,
            apply_filter(
                f.get_documents_queryset()
                .order_by("-created_at")
                .select_related("work")
                .prefetch_related("labels", "taxonomies", "taxonomies__topic")
            ).iterator(max_docs),
        )
        for f in user.following.all()
    ]
    sources = merge_sources_by_date(sources, "created_at")

    # group the (source, document) tuples by date
    n_docs = 0
    groups_by_date = {}
    for day, doc_group in groupby(sources, lambda p: p[1].created_at.date()):
        doc_group = list(doc_group)
        n_docs += len(doc_group)

        # group the days documents by source, and put the smallest groups first
        groups = {}
        for source, doc in doc_group:
            groups.setdefault(source, []).append(doc)

        # cap documents per source
        for source, docs in groups.items():
            docs = sorted(docs, key=lambda d: d.date, reverse=True)
            groups[source] = (docs[:docs_per_source], docs[docs_per_source:])

        # tuples: (source, (docs, rest))
        groups_by_date[day] = sorted(
            groups.items(), key=lambda x: len(x[1][0]) + len(x[1][1])
        )

        if max_docs and n_docs > max_docs:
            break

    return groups_by_date


def merge_sources_by_date(sources, date_attr):
    """Merge multiple following sources into a single iterator of documents, ordered by the date attribute,
    most recent first.

    sources: (source, Iterator[Document])
    Yields (source, document) in descending date order across all sources.
    """

    def pair_generator(source, docs):
        for d in docs:
            yield source, d

    generators = [pair_generator(source, docs) for source, docs in sources]

    # merge the sources by date, reverse=True because we have the largest date first
    return heapq.merge(
        *generators, key=lambda p: getattr(p[1], date_attr), reverse=True
    )
