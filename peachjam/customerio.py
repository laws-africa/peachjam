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

    def track_user_logged_in(self, user):
        if self.enabled():
            self.update_user_details(user)
            analytics.track(
                user.userprofile.tracking_id_str,
                "Logged in",
            )

    def track_user_logged_out(self, user):
        if self.enabled():
            analytics.track(
                user.userprofile.tracking_id_str,
                "Logged out",
            )

    def track_user_signed_up(self, user):
        if self.enabled():
            analytics.track(
                user.userprofile.tracking_id_str,
                "Sign up",
            )

    def update_user_details(self, user):
        """Push user details to customerio"""
        if self.enabled():
            analytics.identify(
                user.userprofile.tracking_id_str, self.get_user_details(user)
            )

    def get_document_track_properties(self, doc):
        """Get the properties for this document that are included with its tracking events."""
        uri = doc.expression_uri()
        return {
            "work_frbr_uri": uri.work_uri(),
            "expression_frbr_uri": uri.expression_uri(),
            "frbr_uri_country": uri.country,
            "frbr_uri_locality": uri.locality,
            "frbr_uri_place": uri.place,
            "frbr_uri_doctype": doc.frbr_uri_doctype,
            "frbr_uri_subtype": doc.frbr_uri_subtype,
            # uri.actor gets confused with subtype
            "frbr_uri_actor": doc.frbr_uri_actor,
            "frbr_uri_date": uri.date,
            "frbr_uri_number": uri.number,
            "frbr_uri_language": uri.language,
        }


_customerio = CustomerIO()


def get_customerio():
    return _customerio
