import json
from collections import namedtuple

from django.contrib import messages
from django.utils.html import format_html

from africanlii.registry import registry
from peachjam.models import Legislation
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["notices"] = self.get_notices()
        return context

    def get_notices(self):
        notices = super().get_notices()

        # Repeal
        if self.object.repealed:
            repeal = self.get_repeal_info()

            notices.append(
                {
                    "type": messages.WARNING,
                    "html": format_html(
                        f"This {self.object.metadata_json['type_name']} was repealed on \
                            {repeal.date} by <a href='{repeal.repealing_uri}'>{repeal.repealing_title}</a>"
                    ),
                }
            )

        # Out-of-date legislation

        # Up-to-date legislation

        return notices

    def get_repeal_info(self):
        repeal_info = json.dumps(self.object.metadata_json["repeal"])
        return json.loads(repeal_info, object_hook=self.custom_metadata_json_decoder)

    def custom_metadata_json_decoder(self, json_data):
        return namedtuple("decoded_metadata_json", json_data.keys())(
            *json_data.values()
        )
