import logging

from countries_plus.models import Country
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from peachjam_search.models import SavedSearch
from peachjam_subs.models import Subscription

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
    saved_search = models.ForeignKey(
        SavedSearch,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="followers",
        verbose_name=_("saved search"),
    )
    saved_document = models.ForeignKey(
        "peachjam.SavedDocument",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="followers",
        verbose_name=_("saved document"),
    )

    last_alerted_at = models.DateTimeField(
        _("last alerted at"), null=True, blank=True, auto_now_add=True
    )

    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    # fields that can be followed
    EVENT_FIELD_MAP = {
        "court": TimelineEvent.EventTypes.NEW_DOCUMENTS,
        "author": TimelineEvent.EventTypes.NEW_DOCUMENTS,
        "court_class": TimelineEvent.EventTypes.NEW_DOCUMENTS,
        "court_registry": TimelineEvent.EventTypes.NEW_DOCUMENTS,
        "country": TimelineEvent.EventTypes.NEW_DOCUMENTS,
        "locality": TimelineEvent.EventTypes.NEW_DOCUMENTS,
        "taxonomy": TimelineEvent.EventTypes.NEW_DOCUMENTS,
        "saved_search": TimelineEvent.EventTypes.SAVED_SEARCH,
        "saved_document": TimelineEvent.EventTypes.NEW_CITATION,
    }
    follow_fields = list(EVENT_FIELD_MAP.keys())

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
            models.UniqueConstraint(
                fields=["user", "saved_search"],
                condition=models.Q(saved_search__isnull=False),
                name="unique_user_saved_search",
            ),
            models.UniqueConstraint(
                fields=["user", "saved_document"],
                condition=models.Q(saved_document__isnull=False),
                name="unique_user_saved_document",
            ),
        ]

    def __str__(self):
        return f"{self.user} follows {self.followed_object}"

    @property
    def description_text(self):
        if self.get_event_type() == TimelineEvent.EventTypes.SAVED_SEARCH:
            return _("New matches for search alert")
        elif self.get_event_type() == TimelineEvent.EventTypes.NEW_DOCUMENTS:
            return _("New documents added for")
        elif self.get_event_type() == TimelineEvent.EventTypes.NEW_CITATION:
            return _("New citations to saved document")

    @property
    def followed_field(self):
        for field in self.follow_fields:
            if getattr(self, field):
                return field

    def get_event_type(self):
        field = self.followed_field
        if field:
            return self.EVENT_FIELD_MAP[field]
        return None

    @property
    def followed_object(self):
        field = self.followed_field
        if field:
            return getattr(self, field)

    def can_add_more_follows(self):
        sub = Subscription.objects.active_for_user(self.user).first()
        if not sub:
            return False
        limit_reached, _ = sub.check_feature_limit("following_limit")
        return not limit_reached

    def clean(self):
        super().clean()

        if not self.saved_search:  # saved searches have their own limit
            if not self.pk and not self.can_add_more_follows():
                raise ValidationError(_("Following limit reached"))

        # Count how many fields are set (not None)
        set_fields = sum(
            1 for field in self.follow_fields if getattr(self, field) is not None
        )

        if set_fields == 0:
            raise ValidationError(
                f"One of the following fields must be set: {' '.join(self.follow_fields)}"
            )

        if set_fields > 1:
            raise ValidationError(
                f"Only one of the following fields can be set:  {' '.join(self.follow_fields)}"
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

    def get_new_followed_documents(self, since=None, limit=10):
        qs = self.get_documents_queryset().preferred_language(
            self.user.userprofile.preferred_language.iso_639_3
        )
        cutoff = since or self.last_alerted_at
        if cutoff:
            qs = qs.filter(created_at__gt=cutoff)
        if qs.exists():
            self.create_timeline_event_for_followed_docs(qs[:limit])
            return True

    def create_timeline_event_for_followed_docs(self, documents):
        # check for unsent event
        event, new = TimelineEvent.objects.get_or_create(
            user_following=self,
            event_type=self.get_event_type(),
            email_alert_sent_at__isnull=True,
        )
        event.subject_documents.add(*documents)
        return event

    def get_new_search_hits(self, since=None, limit=10):
        if self.saved_search:
            hits = self.saved_search.find_new_hits()
            cutoff = since or self.last_alerted_at
            if cutoff:
                hits = [hit for hit in hits if hit.document.created_at > cutoff][:limit]
            if hits and len(hits) > 0:
                self.create_timeline_event_for_search_alert(hits[:limit])
                return True

    def create_timeline_event_for_search_alert(self, hits):
        documents = [hit.document for hit in hits]
        new_hits = []
        for hit in hits:
            hit_dict = hit.as_dict()
            # replace the Django ORM object with the fields we want
            doc = hit.document
            hit_dict["title"] = doc.title
            hit_dict["document"] = {
                "title": getattr(doc, "title", "") or "",
                "blurb": getattr(doc, "blurb", "") or "",
                "flynote": getattr(doc, "flynote", "") or "",
            }
            new_hits.append(hit_dict)
        # check for unsent event
        event, new = TimelineEvent.objects.get_or_create(
            user_following=self,
            event_type=self.get_event_type(),
            email_alert_sent_at__isnull=True,
            defaults={"extra_data": {"hits": new_hits}},
        )
        if not new:
            existing_hits = event.extra_data.get("hits", [])

            # Deduplicate by "id" (latest hit wins if duplicate id appears)
            combined = {hit["id"]: hit for hit in existing_hits}
            for hit in new_hits:
                combined[hit["id"]] = hit

            event.extra_data["hits"] = list(combined.values())
            event.save(update_fields=["extra_data"])

        event.subject_documents.add(*documents)
        return event

    def update_new_citation(self, citation):
        if not self.saved_document:
            return

        # check that the cited document is the saved one
        if citation.target_work != self.saved_document.document.work:
            return

        # check if the user has ever been alerted about this citation
        events = TimelineEvent.objects.filter(
            user_following=self,
            event_type=TimelineEvent.EventTypes.NEW_CITATION,
        )
        document = citation.citing_work.documents.latest_expression()
        for event in events:
            if document in event.subject_documents.all():
                log.info(
                    "User %s has already been alerted about citation from document %s",
                )
                return

        event, new = TimelineEvent.objects.get_or_create(
            user_following=self,
            event_type=TimelineEvent.EventTypes.NEW_CITATION,
            email_alert_sent_at__isnull=True,
        )
        event.subject_documents.add(document)

    @classmethod
    def update_timeline_for_user(cls, user):
        follows = cls.objects.filter(user=user)
        log.info(f"Found {follows.count()} follows for user {user.pk}")
        for follow in follows:
            follow.update_timeline()

    def update_timeline(self):
        updated = False
        if self.get_event_type() == TimelineEvent.EventTypes.NEW_DOCUMENTS:
            updated = self.get_new_followed_documents()

        if self.get_event_type() == TimelineEvent.EventTypes.SAVED_SEARCH:
            updated = self.get_new_search_hits()

        if not updated:
            log.info("No new documents found for follow %s", self)
            return

        log.info(f"Updating timeline event for {self.followed_object}")
        self.last_alerted_at = timezone.now()
        self.save(update_fields=["last_alerted_at"])

    @classmethod
    def update_users_new_citation(cls, citation):
        follows = cls.objects.filter(
            saved_document__document__work=citation.target_work
        )
        log.info(
            f"Found {follows.count()} follows for citation to work {citation.target_work.pk}"
        )
        for follow in follows:
            follow.update_new_citation(citation)
