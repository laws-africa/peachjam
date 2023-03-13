import re

from docpipe.matchers import CitationMatcher


class MncMatcher(CitationMatcher):
    """Finds references to commonly-formatted MNCS of the form [YYYY] COURT NUM

    example: [2022] ZASCA 126
    """

    country_codes = "|".join("BW GH KE LS MW MU MZ NA SN SC ZA SZ TZ UG ZM ZW".split())

    pattern_re = re.compile(
        r"\[(?P<year>\d{4})\]\s+(?P<court>("
        + country_codes
        + r")[A-Z]{1,8})\s+(?P<num>\d+)\b"
    )
    href_pattern = "/akn/{place}/judgment/{court}/{year}/{num}"
    html_candidate_xpath = ".//text()[contains(., '[') and not(ancestor::a)]"
    xml_candidate_xpath = ".//text()[contains(., '[') and not(ancestor::ns:ref)]"

    def href_pattern_args(self, match):
        args = super().href_pattern_args(match)
        args["place"] = args["court"][:2].lower()
        args["court"] = args["court"].lower()
        return args
