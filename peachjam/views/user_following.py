from django import forms
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, FormView, ListView

from peachjam.models import UserFollowing
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
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields:
            self.fields[field].widget = forms.HiddenInput()


class UserFollowingButtonForm(forms.Form):
    court = forms.IntegerField(required=False)
    author = forms.IntegerField(required=False)
    court_class = forms.IntegerField(required=False)
    court_registry = forms.IntegerField(required=False)
    country = forms.IntegerField(required=False)
    locality = forms.IntegerField(required=False)
    taxonomy = forms.IntegerField(required=False)

    def clean(self):
        cleaned_data = super().clean()

        # Enforce "only one follow target"
        set_fields = [f for f in cleaned_data if cleaned_data.get(f)]
        if len(set_fields) == 0:
            raise forms.ValidationError("One follow target must be set")
        if len(set_fields) > 1:
            raise forms.ValidationError("Only one follow target can be set")

        return cleaned_data


class UserFollowingButtonView(SubscriptionRequiredMixin, FormView):
    permission_required = "peachjam.add_userfollowing"
    form_class = UserFollowingButtonForm
    template_name = "peachjam/user_following/_button.html"

    def get_subscription_required_template(self):
        return self.template_name

    def get(self, *args, **kwargs):
        form = UserFollowingButtonForm(self.request.GET)
        if self.request.user.is_authenticated:
            if form.is_valid():
                follow = UserFollowing.objects.filter(
                    **form.cleaned_data, user=self.request.user
                ).first()
                if follow:
                    return HttpResponseRedirect(
                        reverse("user_following_delete", kwargs={"pk": follow.pk})
                        + f"?{self.request.GET.urlencode()}"
                    )
                return HttpResponseRedirect(
                    reverse("user_following_create")
                    + f"?{self.request.GET.urlencode()}"
                )
            return super().get(*args, **kwargs)
        # invalid form, return empty response i.e no button
        return HttpResponse(status=400)


class BaseUserFollowingView(LoginRequiredMixin):
    model = UserFollowing

    def get_queryset(self):
        return self.request.user.following.filter(
            saved_search__isnull=True, saved_document__isnull=True
        )


class UserFollowingListView(BaseUserFollowingView, ListView):
    template_name = "peachjam/user_following/list.html"
    tab = "user_following"


class UserFollowingCreateView(
    BaseUserFollowingView, SubscriptionRequiredMixin, CreateView
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
        return (
            reverse("user_following_delete", kwargs={"pk": self.object.pk})
            + f"?{self.request.GET.urlencode()}"
        )


class UserFollowingDeleteView(
    BaseUserFollowingView, SubscriptionRequiredMixin, DeleteView
):
    template_name = "peachjam/user_following/_delete.html"
    permission_required = "peachjam.delete_userfollowing"

    def get_success_url(self):
        return reverse("user_following_button") + f"?{self.request.GET.urlencode()}"
