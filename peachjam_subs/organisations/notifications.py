from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail import send_mail
from django.db import transaction
from django.urls import reverse
from django.utils.translation import gettext as _


def send_email(subject, body, recipients):
    """Send an email after the current database transaction commits."""
    recipients = sorted({email for email in recipients if email})
    if recipients:
        transaction.on_commit(
            lambda: send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, recipients)
        )


def notify_invitation(invitation):
    try:
        path = reverse("organisation_invitation", args=[invitation.token])
        url = f"https://{Site.objects.get_current().domain}{path}"
    except Exception:
        url = str(invitation.token)
    send_email(
        _("You have been invited to My LawLibrary"),
        _(
            "You have been invited to join %(organisation)s. The invitation "
            "expires on %(expiry)s. Accept it here: %(url)s"
        )
        % {
            "organisation": invitation.organisation.name,
            "expiry": invitation.expires_at.date(),
            "url": url,
        },
        [invitation.email],
    )


def notify_member(user, subject, body):
    send_email(subject, body, [user.email])


def notify_email(email, subject, body):
    send_email(subject, body, [email])
