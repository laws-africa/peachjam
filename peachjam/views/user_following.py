from django import forms
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import Http404, HttpResponse
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, FormView, ListView

from peachjam.models import UserFollowing, pj_settings
from peachjam.views import AtomicPostMixin
from peachjam_subs.mixins import SubscriptionRequiredMixin
from peachjam_subs.models import Subscription


class UserFollowingForm(forms.ModelForm):
    class Meta:
        model = UserFollowing
        fields = (
            "court",
            "author",
            "court_class",
            "court_registry",
            "country",
            "locality",
            "taxonomy",
            "flynote",
            "journal",
            "law_report",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields:
            self.fields[field].widget = forms.HiddenInput()

    def save(self, commit=True):
        if commit and not self.instance.pk:
            # only create if it doesn't already exist
            self.instance, created = UserFollowing.objects.get_or_create(
                **self.cleaned_data, user=self.instance.user
            )
            return self.instance
        return super().save(commit)


class UserFollowingButtonForm(forms.Form):
    court = forms.IntegerField(required=False)
    author = forms.IntegerField(required=False)
    court_class = forms.IntegerField(required=False)
    court_registry = forms.IntegerField(required=False)
    country = forms.IntegerField(required=False)
    locality = forms.IntegerField(required=False)
    taxonomy = forms.IntegerField(required=False)
    flynote = forms.IntegerField(required=False)
    journal = forms.IntegerField(required=False)
    law_report = forms.IntegerField(required=False)

    def clean(self):
        cleaned_data = super().clean()

        # Enforce "only one follow target"
        set_fields = [f for f in cleaned_data if cleaned_data.get(f)]
        if len(set_fields) == 0:
            raise forms.ValidationError("One follow target must be set")
        if len(set_fields) > 1:
            raise forms.ValidationError("Only one follow target can be set")

        self.followed_field = set_fields[0]
        model_field = UserFollowing._meta.get_field(self.followed_field)
        try:
            self.followed_object = model_field.related_model.objects.get(
                pk=cleaned_data[self.followed_field]
            )
        except model_field.related_model.DoesNotExist:
            raise forms.ValidationError("The follow target no longer exists.")

        return cleaned_data


class AllowFollowsMixin:
    def get_follows_disabled_response(self):
        raise Http404("Following is not allowed.")

    def dispatch(self, *args, **kwargs):
        if not pj_settings().follows_enabled:
            return self.get_follows_disabled_response()
        return super().dispatch(*args, **kwargs)


class UserFollowingButtonView(AllowFollowsMixin, SubscriptionRequiredMixin, FormView):
    permission_required = "peachjam.add_userfollowing"
    form_class = UserFollowingButtonForm
    template_name = "peachjam/user_following/_button.html"

    def get_subscription_required_template(self):
        return self.template_name

    def get_follows_disabled_response(self):
        return HttpResponse(status=204)

    def get_button_context(self, form):
        follow = None
        if self.request.user.is_authenticated:
            follow = UserFollowing.objects.filter(
                **form.cleaned_data, user=self.request.user
            ).first()

        return {
            "follow": follow,
            "followed_object": form.followed_object,
            "followed_object_type": UserFollowing._meta.get_field(
                form.followed_field
            ).verbose_name,
            "email_alerts_disabled": self.request.user.is_authenticated
            and self.request.user.userprofile.email_alert_frequency
            == self.request.user.userprofile.EmailAlertFrequency.NONE,
            "email_alert_frequency": (
                self.request.user.userprofile.get_email_alert_frequency_display().lower()
                if self.request.user.is_authenticated
                else None
            ),
        }

    def get_subscription_required_context(self):
        form = UserFollowingButtonForm(self.request.GET)
        if not form.is_valid():
            return {}
        return self.get_button_context(form)

    def get(self, *args, **kwargs):
        form = UserFollowingButtonForm(self.request.GET)
        if not form.is_valid():
            return HttpResponse(status=400)
        return self.render_to_response(self.get_button_context(form))


class BaseUserFollowingView(AllowFollowsMixin, LoginRequiredMixin):
    model = UserFollowing

    def get_queryset(self):
        return self.request.user.following.filter(
            saved_search__isnull=True, saved_document__isnull=True
        )


class UserFollowingListView(BaseUserFollowingView, PermissionRequiredMixin, ListView):
    permission_required = "peachjam.view_userfollowing"
    template_name = "peachjam/user_following/list.html"
    tab = "user_following"


class UserFollowingCreateView(
    AtomicPostMixin, BaseUserFollowingView, SubscriptionRequiredMixin, CreateView
):
    form_class = UserFollowingForm
    template_name = "peachjam/user_following/_create.html"
    permission_required = "peachjam.add_userfollowing"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        instance = UserFollowing()
        instance.user = self.request.user
        kwargs["instance"] = instance
        kwargs["data"] = self.request.GET or self.request.POST
        return kwargs

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        sub = Subscription.objects.active_for_user(self.request.user).first()
        if sub:
            (
                context["following_limit_reached"],
                context["following_upgrade"],
            ) = sub.check_feature_limit("following_limit")
        context["next"] = self.request.GET.get("next") or ""
        context["target"] = self.request.GET.get("target") or ""
        return context

    def get_success_url(self):
        return reverse("user_following_button") + f"?{self.request.GET.urlencode()}"


class UserFollowingDeleteView(
    AtomicPostMixin, BaseUserFollowingView, SubscriptionRequiredMixin, DeleteView
):
    template_name = "peachjam/user_following/_delete.html"
    permission_required = "peachjam.delete_userfollowing"

    def get_success_url(self):
        return reverse("user_following_button") + f"?{self.request.GET.urlencode()}"
