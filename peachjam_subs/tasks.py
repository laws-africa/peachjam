from background_task import background
from django.db import transaction

from peachjam_subs.models import Subscription
from peachjam_subs.organisations.services import organisation_service


@background(queue="peachjam", remove_existing_tasks=True)
@transaction.atomic
def update_subscriptions():
    organisation_service.expire_invitations()
    organisation_service.send_invitation_reminders()
    organisation_service.apply_scheduled_privacy_changes()
    organisation_service.apply_scheduled_organisation_changes()
    Subscription.update_subscriptions()

    from peachjam_subs.limits import purge_expired_subscription_locked_data

    purge_expired_subscription_locked_data()
