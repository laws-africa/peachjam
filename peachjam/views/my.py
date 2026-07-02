import datetime

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models.aggregates import Count
from django.http.response import Http404
from django.views.generic.base import TemplateView

from peachjam.models import Folder, TimelineEvent, pj_settings
from peachjam_subs.limits import get_subscription_locked_data_summary


class CommonContextMixin:
    max_docs = 15

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.request.user.is_authenticated:
            context["folders"] = Folder.objects.filter(user=self.request.user).annotate(
                n_saved_documents=Count("saved_documents")
            )
            timeline, next_before = TimelineEvent.get_user_timeline(self.request.user)

            context["timeline"] = timeline
            context["next_before"] = next_before
            context["timeline_truncated"] = self.timeline_truncated
            context["subscription_locked_data_summary"] = (
                get_subscription_locked_data_summary(self.request.user)
            )

        return context


class MyHomeView(LoginRequiredMixin, CommonContextMixin, TemplateView):
    template_name = "peachjam/my/home.html"
    tab = "my"
    timeline_truncated = False

    def get(self, request, *args, **kwargs):
        if settings.PEACHJAM["DISABLE_ACCOUNTS"]:
            raise Http404()
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["KEY_LINK_PAGE"] = "my_lii"
        return context


class MyFrontpageView(CommonContextMixin, TemplateView):
    """The My LII part of the site homepage that is loaded dynamically."""

    timeline_truncated = True
    max_docs = 5

    def get(self, request, *args, **kwargs):
        if settings.PEACHJAM["DISABLE_ACCOUNTS"]:
            raise Http404()
        return super().get(request, *args, **kwargs)

    def get_template_names(self):
        if self.request.user.is_authenticated:
            return ["peachjam/my/_frontpage.html"]
        return ["peachjam/my/_frontpage_anon.html"]


class MyTimelineView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = "peachjam/user_following/_timeline.html"
    permission_required = "peachjam.view_userfollowing"

    def get(self, request, *args, **kwargs):
        if not pj_settings().follows_enabled:
            raise Http404()
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        try:
            # optional before_date parameter
            before_date = datetime.date.fromisoformat(self.request.GET.get("before"))
        except (TypeError, ValueError):
            before_date = None

        timeline, next_before = TimelineEvent.get_user_timeline(
            self.request.user, before=before_date
        )
        context["timeline"] = timeline
        context["next_before"] = next_before
        return context
