import logging
import uuid
from datetime import timedelta
from urllib.parse import urlencode

from django.contrib.auth.models import User
from django.db import models
from django.shortcuts import reverse
from django.utils.timezone import now

log = logging.getLogger(__name__)


class SearchTrace(models.Model):
    """A search performed by a user."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # this is the name of the search configuration, for tracking changes across versions
    config_version = models.CharField(max_length=50, null=False)
    request_id = models.CharField(max_length=1024, null=True, editable=False)
    previous_search = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, related_name="next_searches"
    )

    user = models.ForeignKey(User, null=True, on_delete=models.CASCADE)
    ip_address = models.CharField(max_length=1024, null=True)
    user_agent = models.CharField(max_length=2048, null=True)

    search = models.CharField(max_length=2048)
    field_searches = models.JSONField(null=True)
    n_results = models.IntegerField()
    page = models.IntegerField()
    filters = models.JSONField(null=True)
    ordering = models.CharField(max_length=1024, null=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    @classmethod
    def prune(cls, days=90):
        cutoff = now() - timedelta(days=days)
        log.info(f"Pruning search traces older than {days} days")
        deleted = cls.objects.filter(created_at__lt=cutoff).delete()
        log.info(f"Deleted: {deleted}")

    class Meta:
        ordering = ("-created_at",)

    def get_search_url(self):
        """Re-build a search URL for this trace."""
        params = {"q": self.search}
        params.update(
            {k: v for k, v in (self.filters.items() or {}) if k != "is_most_recent"}
        )
        params.update({"page": self.page})
        params.update({"ordering": self.ordering})
        return reverse("search:search") + "?" + urlencode(params, doseq=True)


class SearchClick(models.Model):
    """A click on a search result."""

    search_trace = models.ForeignKey(
        SearchTrace, on_delete=models.CASCADE, related_name="clicks"
    )
    frbr_uri = models.CharField(max_length=2048)
    portion = models.CharField(max_length=2048, null=True)
    position = models.IntegerField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
