from django.conf import settings
from django.contrib.sites.models import Site
from django.db import transaction
from django.urls import reverse
from templated_email import send_templated_mail


def send_templated_email(template_name, recipients, context):
    """Send a templated email after the current database transaction commits."""
    recipients = sorted({email for email in recipients if email})
    if recipients:
        transaction.on_commit(
            lambda: send_templated_mail(
                template_name=template_name,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipients,
                context=context,
            )
        )


def send_email(subject, body, recipients):
    """Send a standard organisation notification using the shared email layout."""
    send_templated_email(
        "organisation/notification",
        recipients,
        {"subject": subject, "body": body},
    )


def notify_invitation(invitation):
    """Send an organisation invitation using the shared email template backend."""
    try:
        path = reverse("organisation_invitation", args=[invitation.token])
        url = f"https://{Site.objects.get_current().domain}{path}"
    except Exception:
        url = str(invitation.token)
    send_templated_email(
        "organisation/invitation",
        [invitation.email],
        {
            "organisation": invitation.organisation.name,
            "expiry": invitation.expires_at.date(),
            "invitation_url": url,
        },
    )


def notify_member(user, subject, body):
    """Send a standard organisation notification to a member."""
    send_email(subject, body, [user.email])


def notify_email(email, subject, body):
    """Send a standard organisation notification to an email address."""
    send_email(subject, body, [email])
