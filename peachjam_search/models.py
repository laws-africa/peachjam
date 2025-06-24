import logging
import uuid
from datetime import datetime, timedelta
from math import exp
from urllib.parse import urlencode

from allauth.account import app_settings
from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.http import QueryDict
from django.shortcuts import reverse
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.utils.translation import override
from templated_email import send_templated_mail

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
    mode = models.CharField(max_length=20, null=False, default="text")
    field_searches = models.JSONField(null=True)
    n_results = models.IntegerField()
    page = models.IntegerField()
    filters = models.JSONField(null=True)
    filters_string = models.CharField(max_length=2048, null=True)
    ordering = models.CharField(max_length=1024, null=True)
    suggestion = models.CharField(max_length=20, null=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        permissions = [
            ("can_debug_search", "Can debug search"),
            ("can_download_search", "Can download search results"),
            ("can_semantic_search", "Can use semantic search"),
        ]

    @classmethod
    def prune(cls, days=90):
        cutoff = now() - timedelta(days=days)
        log.info(f"Pruning search traces older than {days} days")
        deleted = cls.objects.filter(created_at__lt=cutoff).delete()
        log.info(f"Deleted: {deleted}")

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
    score = models.FloatField(null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def save(self, *args, **kwargs):
        self.score = exp(-0.1733 * (self.position - 1))
        super().save(*args, **kwargs)


class SavedSearch(models.Model):
    q = models.CharField(max_length=4098)
    filters = models.CharField(max_length=4098, null=True, blank=True)
    note = models.TextField(null=True, blank=True)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="saved_searches"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_alerted_at = models.DateTimeField(null=True, blank=True, auto_now_add=True)

    def __str__(self):
        s = self.q
        f = self.pretty_filters()
        if f:
            s = f"{s} ({f})"
        return s

    def get_filters_dict(self):
        filters = dict(QueryDict(self.filters).lists())
        filters.pop("q", None)
        filters.pop("page", None)
        return filters

    def pretty_filters(self):
        # get_filters_dict().values() is a list of lists, join the values with commas
        return ", ".join(
            [
                ", ".join(values)
                for key, values in self.get_filters_dict().items()
                if key != "sort"
            ]
        )

    def get_sorted_filters_string(self):
        return urlencode(sorted(self.get_filters_dict().items()), doseq=True)

    def clean(self):
        # sort params alphabetically so that the lookup is consistent
        self.filters = self.get_sorted_filters_string()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        filters = self.get_filters_dict()
        filters["q"] = self.q
        return reverse("search:search") + "?" + urlencode(filters, doseq=True)

    def update_and_alert(self):
        hits = self.find_new_hits()
        if hits:
            self.send_alert(hits)
            self.last_alerted_at = now()
            self.save()

    def find_new_hits(self):
        from peachjam_search.engine import SearchEngine
        from peachjam_search.forms import SearchForm
        from peachjam_search.serializers import SearchHit

        params = QueryDict("", mutable=True)
        for key, values in self.get_filters_dict().items():
            if isinstance(values, list):
                for value in values:
                    params.appendlist(key, value)  # Append multiple values
            else:
                params[key] = values
        params["search"] = self.q

        engine = SearchEngine()
        engine.page_size = 20
        form = SearchForm(params)
        form.is_valid()
        form.configure_engine(engine)
        es_response = engine.execute()

        # unpack the hits
        hits = SearchHit.from_es_hits(engine, es_response.hits)
        # fetch document data for hits from the database
        SearchHit.attach_documents(hits, fake_documents=False)
        # only keep those with a document
        hits = [h for h in hits if h.document]

        # get hits that were created later than the last alert
        if self.last_alerted_at:
            hits = [
                hit
                for hit in hits
                if datetime.fromisoformat(hit.document.created_at)
                > self.last_alerted_at
            ]

        return [hit.as_dict() for hit in hits]

    def send_alert(self, hits):
        hits = hits[:10]
        context = {
            "user": self.user,
            "hits": hits,
            "saved_search": self,
            "manage_url_path": reverse("search:saved_search_list"),
        }
        with override(self.user.userprofile.preferred_language.pk):
            send_templated_mail(
                template_name="search_alert",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[self.user.email],
                context=context,
            )


class SearchFeedback(models.Model):
    search_trace = models.ForeignKey(
        SearchTrace, on_delete=models.CASCADE, related_name="search_clicks"
    )
    feedback = models.CharField(_("feedback"), max_length=4096, null=False, blank=False)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE)
    name = models.CharField(_("name"), null=True, blank=True, max_length=1024)
    email = models.EmailField(
        null=True,
        blank=True,
        max_length=app_settings.EMAIL_MAX_LENGTH,
        verbose_name=_("email address"),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.created_at}"
