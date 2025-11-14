import logging

from countries_plus.models import Country
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

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
    )
    author = models.ForeignKey(
        "peachjam.Author",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="followers",
    )
    court_class = models.ForeignKey(
        "peachjam.CourtClass",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="followers",
    )
    court_registry = models.ForeignKey(
        "peachjam.CourtRegistry",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="followers",
    )
    country = models.ForeignKey(
        Country,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="followers",
    )
    locality = models.ForeignKey(
        "peachjam.Locality",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="followers",
    )
    taxonomy = models.ForeignKey(
        "peachjam.Taxonomy",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="followers",
    )
    saved_search = models.ForeignKey(
        SavedSearch,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="followers",
    )

    last_alerted_at = models.DateTimeField(
        _("last alerted at"), null=True, blank=True, auto_now_add=True
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    EVENT_FIELD_MAP = {
        "court": "new_documents",
        "author": "new_documents",
        "court_class": "new_documents",
        "court_registry": "new_documents",
        "country": "new_documents",
        "locality": "new_documents",
        "taxonomy": "new_documents",
        "saved_search": "saved_search",
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
        ]

    def __str__(self):
        return f"{self.user} follows {self.followed_object}"

    # --- simple helpers ---

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
        return self.get_event_type() == "new_documents"

    @property
    def is_saved_search(self):
        return self.get_event_type() == "saved_search"

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
        if not self.saved_search:
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
