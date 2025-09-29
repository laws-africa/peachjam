import json
import logging
import uuid
from datetime import timedelta
from math import exp
from urllib.parse import urlencode

from allauth.account import app_settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.http import QueryDict
from django.shortcuts import reverse
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from peachjam_subs.models import Subscription

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
    q = models.CharField(max_length=4098, null=True, blank=True)
    a = models.CharField(max_length=4098, null=True, blank=True)
    filters = models.CharField(max_length=4098, null=True, blank=True)
    note = models.TextField(null=True, blank=True)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="saved_searches"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # TODO: remove this field after back fill since we now use user following last alerted at
    last_alerted_at = models.DateTimeField(null=True, blank=True, auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(q__isnull=False) | models.Q(a__isnull=False),
                name="at_least_one_field_not_null",
            )
        ]

    def __str__(self):
        s = self.pretty_query()
        f = self.pretty_filters()
        if f:
            s = f"{s} ({f})"
        return s

    def pretty_query(self):
        s = ""
        if self.a:
            a = json.loads(self.a)
            for query in a:
                condition = query["condition"] if "condition" in query else ""
                if query["fields"][0] == "all":
                    s += f"{condition} {query['text']} in any field "
                else:
                    s += f"{condition} {query['text']} in {query['fields']} "
        else:
            s = self.q

        return s.strip()

    def get_filters_dict(self):
        filters = dict(QueryDict(self.filters).lists())
        filters.pop("q", None)
        filters.pop("a", None)
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

    def can_save_more_folders(self):
        sub = Subscription.objects.active_for_user(self.user).first()
        if not sub:
            return False
        limit_reached, _ = sub.check_feature_limit("search_alert_limit")
        return not limit_reached

    def get_sorted_filters_string(self):
        return urlencode(sorted(self.get_filters_dict().items()), doseq=True)

    def clean(self):
        if not self.pk and not self.can_save_more_folders():
            raise ValidationError(_("Search alert limit reached"))

        # sort params alphabetically so that the lookup is consistent
        self.filters = self.get_sorted_filters_string()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        filters = self.get_filters_dict()
        if self.a:
            filters["a"] = self.a
        else:
            filters["q"] = self.q
        return reverse("search:search") + "?" + urlencode(filters, doseq=True)

    def generate_advanced_search_query(self, criteria):
        a = ""

        for criterion in criteria:
            text = (
                f'"{criterion["text"]}"'
                if criterion.get("exact")
                else criterion.get("text", "")
            )

            if criterion.get("condition") == "AND":
                a += " & "
            elif criterion.get("condition") == "OR":
                a += " | "
            elif criterion.get("condition") == "NOT":
                a += " -"

            a += f"({text})"

        return a.strip()

    def generate_advanced_search_params(self, params):
        # Group criteria by fields
        fields = {}
        for criterion in json.loads(self.a):
            if criterion.get("text"):
                for field in criterion.get("fields", []):
                    fields.setdefault(field, []).append(criterion)

        # Set search params for each field
        for field, criteria in fields.items():
            params[f"search__{field}"] = self.generate_advanced_search_query(criteria)

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

        if self.q:
            params["search"] = self.q
        else:
            self.generate_advanced_search_params(params)

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
        return hits


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
