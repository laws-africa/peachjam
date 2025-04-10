from customerio import analytics
from django.conf import settings

analytics.write_key = settings.PEACHJAM["CUSTOMERIO_PYTHON_KEY"]
analytics.host = "https://cdp-eu.customer.io"


class CustomerIO:
    def enabled(self):
        return bool(analytics.write_key)

    def get_user_details(self, user):
        return {
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "is_staff": user.is_staff,
            "language": user.userprofile.preferred_language.iso,
        }

    def update_user_details(self, user):
        """Push user details to customerio"""
        if self.enabled():
            analytics.identify(
                user.userprofile.tracking_id_str, self.get_user_details(user)
            )


_customerio = CustomerIO()


def get_customerio():
    return _customerio
