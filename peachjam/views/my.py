import datetime

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models.aggregates import Count
from django.http.response import Http404
from django.shortcuts import redirect
from django.utils.translation import gettext as _
from django.views.generic.base import TemplateView

from peachjam.forms import EmailAlertFrequencyForm
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

    def dispatch(self, request, *args, **kwargs):
        if not pj_settings().accounts_enabled:
            raise Http404()
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["KEY_LINK_PAGE"] = "my_lii"
        return context


class EmailAlertsView(LoginRequiredMixin, TemplateView):
    template_name = "peachjam/my/email_alerts.html"
    tab = "email_alerts"

    def dispatch(self, request, *args, **kwargs):
        if not pj_settings().accounts_enabled:
            raise Http404()
        return super().dispatch(request, *args, **kwargs)

    def get_form(self, data=None):
        return EmailAlertFrequencyForm(data=data, user=self.request.user)

    def post(self, request, *args, **kwargs):
        form = self.get_form(request.POST)
        if form.is_valid():
            form.save()
            frequency = self.request.user.userprofile.get_email_alert_frequency_display().lower()
            messages.success(
                request,
                _("Your email update frequency has been updated to %(frequency)s.")
                % {"frequency": frequency},
            )
            return redirect("email_alerts")
        return self.render_to_response(self.get_context_data(form=form))

    def get_context_data(self, form=None, **kwargs):
        context = super().get_context_data(**kwargs)
        context["email_alert_frequency_form"] = form or self.get_form()
        return context


class MyFrontpageView(CommonContextMixin, TemplateView):
    """The My LII part of the site homepage that is loaded dynamically."""

    timeline_truncated = True
    max_docs = 5

    def get(self, request, *args, **kwargs):
        if not pj_settings().accounts_enabled:
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
