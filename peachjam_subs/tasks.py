from background_task import background
from django.db import transaction

from peachjam_subs.models import Subscription


@background(queue="peachjam", remove_existing_tasks=True)
@transaction.atomic
def update_subscriptions():
    Subscription.update_subscriptions()
