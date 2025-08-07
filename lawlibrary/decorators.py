from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from lawlibrary.constants import MUNICIPAL_CODES, PROVINCIAL_CODES
from peachjam.decorators import BreadCrumb, JudgmentDecorator, LegislationDecorator


class LawLibraryLJudgmentDecorator(JudgmentDecorator):
    def get_breadcrumbs(self, document):
        crumbs = [
            BreadCrumb(_("Home"), reverse("home_page")),
            BreadCrumb(_("Judgments"), reverse("judgment_list")),
        ]
        if document.court:
            crumbs.append(
                BreadCrumb(
                    document.court.name,
                    document.court.get_absolute_url(),
                )
            )
        crumbs.append(
            BreadCrumb(
                str(document.date.year),
                reverse("court_year", args=[document.court.code, document.date.year]),
            )
        )
        return crumbs


class LawLibraryLegislationDecorator(LegislationDecorator):
    def get_breadcrumbs(self, document):
        crumbs = [
            BreadCrumb(_("Home"), reverse("home_page")),
        ]

        if document.locality:
            if document.locality.code in PROVINCIAL_CODES:
                crumbs.append(
                    BreadCrumb(
                        _("Provincial Legislation"),
                        reverse("locality_legislation"),
                    )
                )
            elif document.locality.code in MUNICIPAL_CODES:
                crumbs.append(
                    BreadCrumb(
                        _("Municipal By-laws"),
                        reverse("municipal_legislation"),
                    )
                )
            else:
                crumbs.append(
                    BreadCrumb(
                        _("Legislation"),
                        reverse("legislation_list"),
                    )
                )
        else:
            crumbs.append(
                BreadCrumb(
                    _("National Legislation"),
                    reverse("legislation_list"),
                )
            )

        return crumbs
