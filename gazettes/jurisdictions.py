from dataclasses import dataclass
from typing import List


@dataclass
class Jurisdiction:
    code: str
    name: str
    parent_code: str = None
    publication: str = "Government Gazette"
    sub_publication_label: str = "Sub-publication"
    sub_publication_required: bool = False
    sub_publications: List[str] = None
    number_short: str = "no"
    number_long: str = "number"
    stitched_supplements: bool = False
    ident_requires_last_page: bool = False

    @property
    def parent(self):
        if self.parent_code:
            return JURISDICTION_MAP[self.parent_code]

    @property
    def full_name(self):
        if self.parent_code:
            return f"{self.name}, {self.parent.name}"
        return self.name

    @property
    def full_name_for_search(self):
        if self.parent_code:
            return f"{self.parent.name} - {self.name}"
        return self.name

    @property
    def children(self):
        return sorted(
            [x for x in JURISDICTIONS if x.parent_code == self.code],
            key=lambda x: x.name,
        )

    @property
    def place_code(self):
        return self.code


JURISDICTIONS = [
    Jurisdiction("dz", "Algeria"),
    Jurisdiction(
        "ao",
        "Angola",
        sub_publications=["Series I", "Series II", "Series III"],
        sub_publication_label="Series",
        sub_publication_required=True,
    ),
    Jurisdiction("bw", "Botswana"),
    Jurisdiction("cg", "Congo", publication="Journal Officiel"),
    Jurisdiction("aa", "African Regional Bodies"),
    Jurisdiction("aa-eac", "East African Community", "aa", publication="Gazette"),
    Jurisdiction(
        "aa-ecowas",
        "Economic Community of West African States",
        "aa",
        publication="Official Journal",
        number_short="vol",
        number_long="volume",
    ),
    Jurisdiction("gh", "Ghana"),
    Jurisdiction("ke", "Kenya"),
    Jurisdiction("ls", "Lesotho"),
    Jurisdiction("mu", "Mauritius"),
    Jurisdiction("mw", "Malawi"),
    Jurisdiction(
        "mz",
        "Mozambique",
        sub_publications=["Series I", "Series II", "Series III"],
        sub_publication_label="Series",
        sub_publication_required=True,
    ),
    Jurisdiction("na", "Namibia"),
    Jurisdiction("ng", "Nigeria"),
    Jurisdiction("rw", "Rwanda"),
    Jurisdiction("sc", "Seychelles", stitched_supplements=True),
    Jurisdiction("sl", "Sierra Leone"),
    Jurisdiction("sz", "Eswatini"),
    Jurisdiction("tz", "Tanzania"),
    Jurisdiction("tz-znz", "Zanzibar", "tz"),
    Jurisdiction("ug", "Uganda"),
    Jurisdiction("zm", "Zambia"),
    # ZW supplements require the date from the last page
    Jurisdiction(
        "zw", "Zimbabwe", ident_requires_last_page=True, stitched_supplements=True
    ),
    Jurisdiction(
        "za",
        "South Africa",
        sub_publications=[
            "Regulation Gazette",
            "Legal Notices A",
            "Legal Notices B",
            "Legal Notices C",
            "Legal Notices D",
        ],
    ),
    Jurisdiction("za-wc", "Western Cape", "za", "Provincial Gazette"),
    Jurisdiction("za-ec", "Eastern Cape", "za", "Provincial Gazette"),
    Jurisdiction("za-gp", "Gauteng", "za", "Provincial Gazette"),
    Jurisdiction("za-kzn", "KwaZulu-Natal", "za", "Provincial Gazette"),
    Jurisdiction("za-lp", "Limpopo", "za", "Provincial Gazette"),
    Jurisdiction("za-mp", "Mpumalanga", "za", "Provincial Gazette"),
    Jurisdiction("za-nw", "North-West", "za", "Provincial Gazette"),
    Jurisdiction("za-nc", "Northern Cape", "za", "Provincial Gazette"),
    Jurisdiction("za-fs", "Free State", "za", "Provincial Gazette"),
    Jurisdiction("za-transvaal", "Transvaal", "za", "Provincial Gazette"),
    Jurisdiction("ng-la", "Lagos State", "ng", "Official Gazette"),
    Jurisdiction("ma", "Morocco", publication="Bulletin Officiel"),
    Jurisdiction("so", "Somalia"),
    Jurisdiction("so-sl", "Somaliland", "so", "Official Gazette"),
]
JURISDICTION_MAP = {x.code: x for x in JURISDICTIONS}
JURISDICTION_CHOICES = [(x.code, x.name) for x in JURISDICTIONS]

COMMUNITIES = {"aa-eac", "aa-ecowas"}

CONTRIBUTORS = {
    "sz": [
        {
            "name": "Werksmans",
            "url": "https://www.werksmans.com/",
            "img": "werksmans-logo.png",
        }
    ],
    "bw": [
        {
            "name": "Werksmans",
            "url": "https://www.werksmans.com/",
            "img": "werksmans-logo.png",
        }
    ],
    "za": [
        {
            "name": "GIZ",
            "url": "https://www.giz.de/",
            "img": "giz-logo.gif",
        },
        {
            "name": "Webber Wentzel",
            "url": "https://www.webberwentzel.com",
            "img": "ww-logo.png",
        },
        {
            "name": "JSA Library",
            "url": "https://johannesburgbar.co.za/library",
            "img": "jsa.webp",
        },
    ],
    "za-fs": [
        {
            "name": "Free State Province",
            "url": "http://www.premier.fs.gov.za",
            "img": "za-fs-logo.jpg",
        }
    ],
    "zw": [
        {
            "name": "Veritas Zimbabwe",
            "url": "https://www.veritaszim.net/",
            "img": "veritas-logo.png",
        }
    ],
    None: [
        {
            "name": "The Indigo Trust",
            "url": "https://indigotrust.org.uk/",
            "img": "indigo-trust-logo.jpg",
        },
        {
            "name": "UCT Government Publications",
            "url": "http://www.governmentpublications.lib.uct.ac.za/",
            "img": "uct-logo.png",
        },
        {
            "name": "C4ADS",
            "url": "https://c4ads.org",
            "img": "c4ads-logo.png",
        },
    ],
}
ALL_CONTRIBUTORS = sorted(
    list({c["name"]: c for x in CONTRIBUTORS.values() for c in x}.values()),
    key=lambda c: c["name"],
)


def get_country_locality(code):
    from countries_plus.models import Country

    from peachjam.models import Locality

    if "-" in code:
        ctry, loc = code.split("-", 1)
    else:
        ctry = code
        loc = None

    ctry = Country.objects.get(pk=ctry.upper())
    if loc:
        loc = Locality.objects.get(jurisdiction=ctry, code=loc)

    return ctry, loc


def jurisdiction_list():
    """List of (code, name) tuples for active jurisdictions."""
    return sorted(JURISDICTIONS, key=lambda j: j.name)
