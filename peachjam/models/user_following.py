import logging

from countries_plus.models import Country
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from peachjam.models.core_document import CoreDocument
from peachjam.models.timeline import TimelineEvent
from peachjam_search.models import SavedSearch
from peachjam_subs.models import Subscription

log = logging.getLogger(__name__)


class UserFollowing(models.Model):

    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="following",
        verbose_name=_("user"),
    )

    # all the followable objects
    court = models.ForeignKey(
        "peachjam.Court",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="followers",
        verbose_name=_("court"),
    )
    author = models.ForeignKey(
        "peachjam.Author",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="followers",
        verbose_name=_("author"),
    )
    court_class = models.ForeignKey(
        "peachjam.CourtClass",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="followers",
        verbose_name=_("court class"),
    )
    court_registry = models.ForeignKey(
        "peachjam.CourtRegistry",
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
        "peachjam.Locality",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="followers",
        verbose_name=_("locality"),
    )
    taxonomy = models.ForeignKey(
        "peachjam.Taxonomy",
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
        return f"{self.user} follows {self.followed_field} {self.followed_object}"

    # --- simple helpers ---

    @property
    def description_text(self):
        if self.get_event_type() == TimelineEvent.EventTypes.SAVED_SEARCH:
            return _("New matches for search alert")
        elif self.get_event_type() == TimelineEvent.EventTypes.NEW_DOCUMENTS:
            return _("New documents added for")
        elif self.get_event_type() == TimelineEvent.EventTypes.NEW_CITATION:
            return _("New citations of")

    @property
    def followed_field(self):
        for f in self.follow_fields:
            if getattr(self, f):
                return f

    @property
    def followed_object(self):
        field = self.followed_field
        return getattr(self, field) if field else None

    def get_event_type(self):
        field = self.followed_field
        return self.EVENT_FIELD_MAP.get(field)

    @property
    def is_new_docs(self):
        return self.get_event_type() == TimelineEvent.EventTypes.NEW_DOCUMENTS

    @property
    def is_saved_search(self):
        return self.get_event_type() == TimelineEvent.EventTypes.SAVED_SEARCH

    @property
    def cutoff_date(self):
        cutoff_days = 365
        return (timezone.now() - timezone.timedelta(days=cutoff_days)).date()

    # --- validation only ---

    def can_add_more_follows(self):
        sub = Subscription.objects.active_for_user(self.user).first()
        if not sub:
            return False
        limit_reached, _ = sub.check_feature_limit("following_limit")
        return not limit_reached

    def clean(self):
        super().clean()

        # enforce subscription limits
        if not (self.saved_search or self.saved_document):
            if not self.pk and not self.can_add_more_follows():
                raise ValidationError(_("Following limit reached"))

        # ensure only one field is set
        set_fields = sum(
            1 for field in self.follow_fields if getattr(self, field) is not None
        )
        if set_fields == 0:
            raise ValidationError(
                f"One of: {' '.join(self.follow_fields)} must be set."
            )
        if set_fields > 1:
            raise ValidationError(
                f"Only one of: {' '.join(self.follow_fields)} can be set."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def documents_for_followed_topic(self):
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
            topics = [self.taxonomy] + list(self.taxonomy.get_descendants())
            return qs.filter(taxonomies__topic__in=topics)

        return qs.none()

    def documents_for_followed_search(self):
        return self.saved_search.find_new_hits()

    def update_follow(self):
        if self.is_new_docs:
            return self._update_new_docs()

        if self.is_saved_search:
            return self._update_search()

    def _update_new_docs(self):
        qs = self.documents_for_followed_topic()
        qs = qs.preferred_language(self.user.userprofile.preferred_language.iso_639_3)

        if self.last_alerted_at:
            qs = qs.filter(created_at__gt=self.last_alerted_at)

        # avoid alerts for documents older than cutoff
        qs = qs.filter(date=self.cutoff_date)

        docs = list(qs[:10])
        if not docs:
            return False

        TimelineEvent.add_new_documents_event(self, docs)
        self.last_alerted_at = timezone.now()
        self.save(update_fields=["last_alerted_at"])
        return True

    def _update_search(self):
        hits = self.documents_for_followed_search()

        # avoid alerts for documents older than cutoff
        hits = [h for h in hits if h.document.date >= self.cutoff_date]

        if self.last_alerted_at:
            hits = [h for h in hits if h.document.created_at > self.last_alerted_at][
                :10
            ]

        if not hits:
            return False

        TimelineEvent.add_new_search_hits_event(self, hits)
        self.last_alerted_at = timezone.now()
        self.save(update_fields=["last_alerted_at"])
        return True

    def _update_new_citation(self, citation):
        assert self.saved_document

        # check that we are passing a citation to the saved document
        assert citation.target_work == self.saved_document.work

        # avoid alerts for citations from documents older than cutoff
        if citation.citing_work.date < self.cutoff_date:
            log.info(
                "Citation from work %s is older than cutoff date for user %s",
                citation.citing_work,
                self.user,
            )
            return

        # check if the user has ever been alerted about this citation
        already_alerted = TimelineEvent.objects.filter(
            user_following=self,
            event_type=TimelineEvent.EventTypes.NEW_CITATION,
            subject_works=citation.citing_work,
        ).exists()
        if already_alerted:
            log.info(
                "User %s has already been alerted about citation from work %s",
                self.user,
                citation.citing_work,
            )
            return
        TimelineEvent.add_new_citation_events(self, citation.citing_work)

    @classmethod
    def update_follows_for_user(cls, user):
        follows = user.following.all()
        for follow in follows:
            follow.update_follow()

    @classmethod
    def update_new_citation_follows(cls, citation):
        follows = cls.objects.filter(
            saved_document__work=citation.target_work,
        )
        log.info("Found %d follows for new citation update", follows.count())
        for follow in follows:
            follow._update_new_citation(citation)
