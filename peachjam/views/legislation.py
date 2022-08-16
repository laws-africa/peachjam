from datetime import datetime, timedelta

from django.contrib import messages
from django.utils.html import format_html

from peachjam.models import Legislation
from peachjam.registry import registry
from peachjam.views.generic_views import (
    BaseDocumentDetailView,
    FilteredDocumentListView,
)


class LegislationListView(FilteredDocumentListView):
    model = Legislation
    template_name = "peachjam/legislation_list.html"
    context_object_name = "documents"
    paginate_by = 20


@registry.register_doc_type("legislation")
class LegislationDetailView(BaseDocumentDetailView):
    model = Legislation
    template_name = "peachjam/legislation_detail.html"

    def get_notices(self):
        notices = super().get_notices()
        repeal = self.get_repeal_info()
        friendly_type = self.object.metadata_json["type_name"]

        if self.object.repealed and repeal:
            msg = "This {} was repealed on {} by <a href='{}'>{}</a>."
            notices.append(
                {
                    "type": messages.ERROR,
                    "html": format_html(
                        msg.format(
                            friendly_type,
                            repeal["date"],
                            repeal["repealing_uri"],
                            repeal["repealing_title"],
                        )
                    ),
                }
            )

        current_object_date = self.object.date.strftime("%Y-%m-%d")

        points_in_time = self.get_points_in_time()
        dates = [point_in_time["date"] for point_in_time in points_in_time]
        index = dates.index(current_object_date)

        if index == len(dates) - 1:
            if self.object.repealed and repeal:
                msg = "This is the version of this {} as it was when it was repealed."
            else:
                msg = "This is the latest version of this {}."

            notices.append(
                {
                    "type": messages.INFO,
                    "html": format_html(msg.format(friendly_type)),
                }
            )
        else:
            date = datetime.strptime(dates[index + 1], "%Y-%m-%d").date() - timedelta(
                days=1
            )

            if self.object.repealed and repeal:
                msg = (
                    "This is the version of this {} as it was from {} to {}. "
                    "<a href='{}'>Read the version as it was when it was repealed.</a>"
                )
            else:
                msg = (
                    "This is the version of this {} as it was from {} to {}. "
                    "<a href='{}'>Read the version currently in force.</a>"
                )

            notices.append(
                {
                    "type": messages.WARNING,
                    "html": format_html(
                        msg.format(
                            friendly_type,
                            current_object_date,
                            date,
                            points_in_time[-1]["expressions"][0]["expression_frbr_uri"],
                        )
                    ),
                }
            )

        return notices

    def get_repeal_info(self):
        return self.object.metadata_json.get("repeal", None)

    def get_points_in_time(self):
        return self.object.metadata_json.get("points_in_time", None)
