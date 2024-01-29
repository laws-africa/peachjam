from django.conf import settings


class RedirectResolver:
    RESOLVER_MAPPINGS = {
        "africanlii": {
            "country_code": "aa",
            "domain": "africanlii.org",
        },
        "civlii": {
            "country_code": "ci",
            "domain": "civlii.laws.africa",
        },
        "eswatinilii": {
            "country_code": "sz",
            "domain": "eswatinilii.org",
        },
        "ghalii": {
            "country_code": "gh",
            "domain": "ghalii.org",
        },
        "lawlibrary": {
            "country_code": "za",
            "domain": "lawlibrary.org.za",
        },
        "leslii": {
            "country_code": "ls",
            "domain": "lesotholii.org",
        },
        "malawilii": {
            "country_code": "mw",
            "domain": "malawilii.org",
        },
        "mauritiuslii": {
            "country_code": "mu",
            "domain": "mauritiuslii.org",
        },
        "namiblii": {
            "country_code": "na",
            "domain": "namiblii.org",
        },
        "nigerialii": {
            "country_code": "ng",
            "domain": "nigerialii.org",
        },
        "open by-laws": {
            "place_code": [],
            "domain": "openbylaws.org.za",
        },
        "rwandalii": {
            "country_code": "rw",
            "domain": "rwandalii.org",
        },
        "seylii": {
            "country_code": "sc",
            "domain": "seylii.org",
        },
        "sierralii": {
            "country_code": "sl",
            "domain": "sierralii.org",
        },
        "tanzlii": {
            "country_code": "tz",
            "domain": "tanzlii.org",
        },
        "tcilii": {
            "country_code": "tc",
            "domain": "tcilii.org",
        },
        "ulii": {
            "country_code": "ug",
            "domain": "ulii.org",
        },
        "zambialii": {
            "country_code": "zm",
            "domain": "zambialii.org",
        },
        "zanzibarlii": {
            "place_code": "tz-znz",
            "domain": "zanzibarlii.org",
        },
        "zimlii": {
            "country_code": "zw",
            "domain": "zimlii.org",
        },
    }

    def __init__(self, app_name):
        self.current_authority = self.RESOLVER_MAPPINGS.get(app_name.lower())

    def get_domain_for_frbr_uri(self, parsed_frbr_uri):
        best_domain = self.get_best_domain(parsed_frbr_uri)
        if self.current_authority and best_domain != self.current_authority["domain"]:
            return best_domain
        return None

    def get_url_for_frbr_uri(self, parsed_frbr_uri, raw_frbr_uri):
        domain = self.get_domain_for_frbr_uri(parsed_frbr_uri)
        if domain:
            return f"https://{domain}{raw_frbr_uri}"

    def get_best_domain(self, parsed_uri):
        country_code = parsed_uri.country
        place_code = parsed_uri.place

        if country_code != place_code:
            for key, mapping in self.RESOLVER_MAPPINGS.items():
                if mapping.get("place_code") == place_code:
                    return mapping.get("domain")

        # if no domain matching with place code is found use country code
        for key, mapping in self.RESOLVER_MAPPINGS.items():
            if mapping.get("country_code") == country_code:
                return mapping.get("domain")
        return None


resolver = RedirectResolver(settings.PEACHJAM["APP_NAME"])
