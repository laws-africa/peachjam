import re

from docpipe.matchers import CitationMatcher, ExtractedMatch


class MncMatcher(CitationMatcher):
    """Finds references to commonly-formatted MNCS of the form [YYYY] COURT NUM

    example: [2022] ZASCA 126
    """

    country_codes = "|".join(
        # Africa
        "BW GH KE LS MW MU MZ NA SN SC ZA SZ TZ UG ZM ZW".split()
        # Caribbean
        + ["TC"]
    )

    pattern_re = re.compile(
        r"\[(?P<year>\d{4})\]\s+(?P<court>("
        + country_codes
        + r")[A-Z]{1,8})\s+(?P<num>\d+)\b"
    )
    href_pattern = "/akn/{place}/judgment/{court}/{year}/{num}"
    html_candidate_xpath = ".//text()[contains(., '[') and not(ancestor::a)]"
    xml_candidate_xpath = ".//text()[contains(., '[') and not(ancestor::ns:ref)]"

    locality_court_codes = {
        "za": {
            "ec": "ec",
            "fs": "fs",
            "gp": "gp",
            "kz": "kzn",
            "lmp": "lp",
            "mp": "mp",
            "nc": "nc",
            "nw": "nw",
            "wc": "wc",
        }
    }

    def make_href(self, match: ExtractedMatch):
        if self.frbr_uri.country == "gh" and match.groups["court"].lower()[:2] == "sc":
            # In Ghana SCxx is a law report, not a Seychelles court
            return None
        return super().make_href(match)

    def href_pattern_args(self, match):
        args = super().href_pattern_args(match)
        args["court"] = court = args["court"].lower()
        args["place"] = court[:2]

        # some court codes embed a locality that we must take into account
        codes = self.locality_court_codes.get(args["place"], {})
        for court_code, locality_code in codes.items():
            if court[2 : 2 + len(court_code)] == court_code:
                args["place"] = f"{args['place']}-{locality_code}"
                break

        return args
