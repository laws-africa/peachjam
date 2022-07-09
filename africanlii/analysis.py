import re

from peachjam.analysis.citations import citation_analyser
from peachjam.analysis.matchers import CitationMatcher


class AchprResolutionMatcher(CitationMatcher):
    """Finds references to ACHPR resolutions in documents, of the form:

    ACHPR/Res.227 (LII) 2012
    ACHPR/Res. 437 (EXT.OS/ XXVI1) 2020
    ACHPR/Res.79 (XXXVIII) 05
    """

    pattern_re = re.compile(
        r"""\bACHPR/Res\.?\s*
            (?P<num>\d+)\s*
            \((EXT\.\s*OS\s*/\s*)?[XVILC1]+\)\s*
            (?P<year>\d{2,4})
        """,
        re.X | re.I,
    )
    candidate_xpath = ".//text()[contains(., 'ACHPR') and not(ancestor::a)]"

    href_pattern = "/akn/aa-au/statement/resolution/achpr/{year}/{num}"

    def href_pattern_args(self, match):
        args = super().href_pattern_args(match)

        # adjust for short years
        year = int(args["year"])
        if year < 100:
            if year > 80:
                year = 1900 + year
            else:
                year = 2000 + year
            args["year"] = str(year)

        return args


# TODO: Act 5 of 2019 matcher, use whatever marker is appropriate
# TODO: for plain text, we care about the regex and how to extract the right run and FRBR URI from it
# TODO: for html, we care about the regex and how to markup the right run and FRBR URI from it
citation_analyser.matchers.append(AchprResolutionMatcher)
