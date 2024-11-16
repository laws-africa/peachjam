import logging
import uuid
from datetime import timedelta
from math import exp
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.core.mail import send_mail
from django.db import models
from django.http import QueryDict
from django.shortcuts import reverse
from django.template.loader import render_to_string
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from rest_framework.test import APIRequestFactory

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
    filters_string = models.CharField(max_length=2048, null=True)
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
    score = models.FloatField(null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def save(self, *args, **kwargs):
        self.score = exp(-0.1733 * (self.position - 1))
        super().save(*args, **kwargs)


class SavedSearch(models.Model):
    q = models.CharField(max_length=4098)
    filters = models.CharField(max_length=4098)
    note = models.TextField(null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateField(auto_now_add=True)
    last_alert = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.q

    def update_and_alert(self):
        hits = self.find_new_hits()
        if hits:
            self.send_alert(hits)
            self.last_alert = now()
            self.save()

    def find_new_hits(self):
        from peachjam_search.views import DocumentSearchViewSet

        factory = APIRequestFactory()
        request = factory.get("/search/api/documents/")
        request.user = self.user
        params = f"q={self.q}&{self.filters}&created_at__gte={self.last_alert.replace(tzinfo=None).isoformat()}"
        request.GET = QueryDict(params)
        request.id = "none"
        view = DocumentSearchViewSet.as_view({"get": "list"})
        response = view(request)
        hits = response.data["results"]
        return hits

    def send_alert(self, hits):
        # send an email or other alert to the user
        hits = hits[:10]
        context = {
            "hits": hits,
            "saved_search": self,
            "site": Site.objects.get_current(),
        }
        html = render_to_string("peachjam_search/emails/search_alert.html", context)
        plain_txt = render_to_string("peachjam_search/emails/search_alert.txt", context)

        subject = settings.EMAIL_SUBJECT_PREFIX + _("New hits for search ") + self.q
        send_mail(
            subject=subject,
            message=plain_txt,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[self.user.email],
            html_message=html,
            fail_silently=False,
        )
