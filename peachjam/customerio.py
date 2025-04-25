from customerio import analytics
from django.conf import settings

analytics.write_key = settings.PEACHJAM["CUSTOMERIO_PYTHON_KEY"]
analytics.host = "https://cdp-eu.customer.io"


class CustomerIO:
    def enabled(self):
        return bool(analytics.write_key)

    def get_common_details(self):
        """Details pushed for all events."""
        # if this is changed, ensure the same details are added to CustomerIO in peachjam/js/analytics.ts
        return {
            "app_name": settings.PEACHJAM["APP_NAME"],
        }

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

    def get_saved_document_details(self, saved_doc):
        details = self.get_document_track_properties(saved_doc.document)
        details.update(self.get_common_details())
        return details

    def get_user_following_details(self, user_following):
        details = self.get_common_details()
        details["followed_type"] = user_following.followed_field
        details["followed_name"] = str(user_following.followed_object)
        return details

    def get_annotation_details(self, annotation):
        details = self.get_document_track_properties(annotation.document)
        details.update(self.get_common_details())
        return details

    def get_user_details(self, user):
        details = {
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "is_staff": user.is_staff,
            "language": user.userprofile.preferred_language.iso,
        }
        details.update(self.get_common_details())
        return details

    def track_user_logged_in(self, user):
        if self.enabled():
            self.update_user_details(user)
            analytics.track(
                user.userprofile.tracking_id_str,
                "Logged in",
                self.get_common_details(),
            )

    def track_user_logged_out(self, user):
        if self.enabled():
            analytics.track(
                user.userprofile.tracking_id_str,
                "Logged out",
                self.get_common_details(),
            )

    def track_user_signed_up(self, user):
        if self.enabled():
            analytics.track(
                user.userprofile.tracking_id_str,
                "Signed up",
                self.get_common_details(),
            )

    def track_saved_search(self, saved_search):
        if self.enabled():
            analytics.track(
                saved_search.user.userprofile.tracking_id_str,
                "Saved search",
                self.get_common_details(),
            )

    def track_unsaved_search(self, saved_search):
        if self.enabled():
            analytics.track(
                saved_search.user.userprofile.tracking_id_str,
                "Unsaved search",
                self.get_common_details(),
            )

    def track_saved_document(self, saved_doc):
        if self.enabled():
            analytics.track(
                saved_doc.user.userprofile.tracking_id_str,
                "Saved document",
                self.get_saved_document_details(saved_doc),
            )

    def track_unsaved_document(self, saved_doc):
        if self.enabled():
            analytics.track(
                saved_doc.user.userprofile.tracking_id_str,
                "Unsaved document",
                self.get_saved_document_details(saved_doc),
            )

    def track_follow(self, user_following):
        if self.enabled():
            analytics.track(
                user_following.user.userprofile.tracking_id_str,
                "Started following",
                self.get_user_following_details(user_following),
            )

    def track_unfollow(self, user_following):
        if self.enabled():
            analytics.track(
                user_following.user.userprofile.tracking_id_str,
                "Stopped following",
                self.get_user_following_details(user_following),
            )

    def track_annotated(self, annotation):
        if self.enabled():
            analytics.track(
                annotation.user.userprofile.tracking_id_str,
                "Annotated a document",
                self.get_annotation_details(annotation),
            )

    def track_unannotated(self, annotation):
        if self.enabled():
            analytics.track(
                annotation.user.userprofile.tracking_id_str,
                "Unannotated a document",
                self.get_annotation_details(annotation),
            )

    def track_password_reset_started(self, user):
        if self.enabled():
            analytics.track(
                user.userprofile.tracking_id_str,
                "Password reset started",
                self.get_common_details(),
            )

    def track_password_reset(self, user):
        if self.enabled():
            analytics.track(
                user.userprofile.tracking_id_str,
                "Password reset",
                self.get_common_details(),
            )

    def update_user_details(self, user):
        """Push user details to customerio"""
        if self.enabled():
            analytics.identify(
                user.userprofile.tracking_id_str, self.get_user_details(user)
            )


_customerio = CustomerIO()


def get_customerio():
    return _customerio
