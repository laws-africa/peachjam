import logging

from peachjam.adapters import RequestsAdapter
from peachjam.models import Ratification, RatificationCountry, Work, pj_settings
from peachjam.plugins import plugins

log = logging.getLogger(__name__)


@plugins.register("ingestor-adapter")
class RatificationsAdapter(RequestsAdapter):
    """Fetches (update-only) ratifications from different LII websites.

    settings required:
    - api_url
    - token
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.jurisdiction = self.settings.get("jurisdiction")
        self.client.headers.update(
            {
                "Authorization": f"Token {self.settings['token']}",
            }
        )

    def check_for_updates(self, last_refreshed):
        # just get all ratifications, we don't care if they have changed (it's a small set)
        ratifications = self.get_ratifications()

        # now ensure that our ratifications are up-to-date
        self.update_ratifications(ratifications)

    def get_ratifications(self):
        results = []
        url = f"{self.api_url}/ratifications.json"
        while url:
            res = self.client_get(url).json()
            results.extend(res["results"])
            url = res["next"]
        return results

    def update_ratifications(self, ratifications):
        jurisdictions = {j.pk: j for j in pj_settings().document_jurisdictions.all()}

        for ratification_data in ratifications:
            log.info(f"Updating ratification: {ratification_data}")
            work_frbr_uri = ratification_data["work"]
            countries_data = ratification_data["countries"]

            work = Work.objects.filter(frbr_uri=work_frbr_uri).first()
            if not work:
                log.info(f"Work {work_frbr_uri} not found, skipping ratification")

            ratification, _ = Ratification.objects.update_or_create(work=work)

            for country_data in countries_data:
                if country_data["country"] not in jurisdictions:
                    log.warning(
                        f"Country {country_data['country']} not found in jurisdictions, skipping"
                    )
                    continue

                RatificationCountry.objects.update_or_create(
                    ratification=ratification,
                    country=jurisdictions[country_data["country"]],
                    defaults={
                        "ratification_date": country_data["ratification_date"],
                        "deposit_date": country_data["deposit_date"],
                        "signature_date": country_data["signature_date"],
                    },
                )
