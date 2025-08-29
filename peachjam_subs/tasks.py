from background_task import background

from peachjam_subs.models import Subscription


@background(queue="peachjam", remove_existing_tasks=True)
def update_subscriptions():
    Subscription.update_subscriptions()
