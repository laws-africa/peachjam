import uuid

from django import forms
from django.utils.translation import gettext_lazy as _

from peachjam_subs.models import OffboardingFeedback


class OffboardingFeedbackForm(forms.Form):
    confirmation_token = forms.UUIDField(required=False, widget=forms.HiddenInput)
    reason = forms.ChoiceField(
        label=_("What is the main reason for this change?"),
        choices=OffboardingFeedback.Reason.choices,
        widget=forms.RadioSelect,
    )
    comment = forms.CharField(
        label=_("Tell us more (optional)"),
        max_length=2000,
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["confirmation_token"].initial = uuid.uuid4()

    def clean(self):
        cleaned_data = super().clean()
        if (
            cleaned_data.get("reason") == OffboardingFeedback.Reason.OTHER
            and not cleaned_data.get("comment", "").strip()
        ):
            self.add_error("comment", _("Please tell us briefly why."))
        return cleaned_data

    def record_downgrade(self, user, current_subscription, requested_product_offering):
        return OffboardingFeedback.record_downgrade(
            user=user,
            current_subscription=current_subscription,
            requested_product_offering=requested_product_offering,
            reason=self.cleaned_data["reason"],
            comment=self.cleaned_data["comment"].strip(),
            confirmation_token=self.cleaned_data["confirmation_token"] or uuid.uuid4(),
        )

    def record_account_deletion(self):
        return OffboardingFeedback.record_account_deletion(
            reason=self.cleaned_data["reason"],
            comment=self.cleaned_data["comment"].strip(),
        )
