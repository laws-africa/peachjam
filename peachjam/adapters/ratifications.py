import logging

from countries_plus.models import Country

from peachjam.adapters import RequestsAdapter
from peachjam.models import Ratification, RatificationCountry, Work
from peachjam.plugins import plugins

log = logging.getLogger(__name__)


@plugins.register("ingestor-adapter")
class RatificationsAdapter(RequestsAdapter):
    """Fetches (update-only) ratifications from different LII websites.

    settings:
    - api_url
    - token
    - exclude_countries - space-separated list of country codes to exclude
    - include_countries - space-separated list of country codes to include
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.jurisdiction = self.settings.get("jurisdiction")
        self.client.headers.update(
            {
                "Authorization": f"Token {self.settings['token']}",
            }
        )
        self.exclude_countries = (
            self.settings.get("exclude_countries", "").lower().split()
        )
        self.include_countries = (
            self.settings.get("include_countries", "").lower().split()
        )

    def check_for_updates(self, last_refreshed):
        # just get all ratifications, we don't care if they have changed (it's a small set)
        ratifications = self.get_ratifications()

        # now ensure that our ratifications are up-to-date
        self.update_ratifications(ratifications)

        return [], []

    def get_ratifications(self):
        results = []
        url = f"{self.api_url}/ratifications.json"
        while url:
            res = self.client_get(url).json()
            results.extend(res["results"])
            url = res["next"]
        return results

    def update_ratifications(self, ratifications):
        for ratification_data in ratifications:
            log.info(f"Updating ratification: {ratification_data}")
            work_frbr_uri = ratification_data["work"]
            countries_data = ratification_data["countries"]

            work = Work.objects.filter(frbr_uri=work_frbr_uri).first()
            if not work:
                log.info(f"Work {work_frbr_uri} not found, skipping ratification")
                continue

            ratification, _ = Ratification.objects.get_or_create(work=work)

            for country_data in countries_data:
                country_code = country_data["country"].lower()
                if (
                    self.include_countries
                    and country_code not in self.include_countries
                ):
                    log.warning(
                        f"Ignoring country {country_code} not in include_countries"
                    )
                    continue

                if self.exclude_countries and country_code in self.exclude_countries:
                    log.warning(f"Ignoring country {country_code} in exclude_countries")
                    continue

                country = Country.objects.filter(pk=country_code.upper()).first()
                if not country:
                    log.warning(f"Country {country_code} not found, skipping")
                    continue

                RatificationCountry.objects.update_or_create(
                    ratification=ratification,
                    country=country,
                    defaults={
                        "ratification_date": country_data["ratification_date"],
                        "deposit_date": country_data["deposit_date"],
                        "signature_date": country_data["signature_date"],
                    },
                )
