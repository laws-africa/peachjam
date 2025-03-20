from django import forms
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, ListView, TemplateView

from peachjam.models import UserFollowing


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


class UserFollowingButtonView(TemplateView):
    template_name = "peachjam/user_following_button.html"

    def get(self, *args, **kwargs):
        form = UserFollowingForm(self.request.GET)
        if form.is_valid():
            if self.request.user.is_authenticated:
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


class BaseUserFollowingView(LoginRequiredMixin, PermissionRequiredMixin):
    model = UserFollowing

    def get_queryset(self):
        return self.request.user.following.all()


class UserFollowingListView(BaseUserFollowingView, ListView):
    permission_required = "peachjam.view_userfollowing"
    template_name = "peachjam/user_following_list.html"


class UserFollowingCreateView(BaseUserFollowingView, CreateView):
    form_class = UserFollowingForm
    template_name = "peachjam/user_following_create.html"
    permission_required = "peachjam.add_userfollowing"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        instance = UserFollowing()
        instance.user = self.request.user
        kwargs["instance"] = instance
        kwargs["data"] = self.request.GET or self.request.POST
        return kwargs

    def get_success_url(self):
        return (
            reverse("user_following_delete", kwargs={"pk": self.object.pk})
            + f"?{self.request.GET.urlencode()}"
        )


class UserFollowingDeleteView(BaseUserFollowingView, DeleteView):
    template_name = "peachjam/user_following_delete.html"
    permission_required = "peachjam.delete_userfollowing"

    def get_success_url(self):
        return reverse("user_following_button") + f"?{self.request.GET.urlencode()}"
