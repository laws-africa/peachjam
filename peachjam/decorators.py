from dataclasses import dataclass

from django.conf import settings
from django.urls import reverse
from django.utils.translation import gettext_lazy as _


@dataclass
class BreadCrumb:
    """A simple dataclass to represent a breadcrumb."""

    name: str
    url: str


class DocumentDecorator:
    """Decorators are mini plugins that allow you to add extra functionality to your documents."""

    def pre_save(self, document):
        """Called before a document is saved."""
        pass

    def post_save(self, document):
        """Called after a document is saved."""
        self.apply_labels(document)

    def apply_labels(self, document):
        pass

    def get_breadcrumbs(self, document):
        """Get a list of breadcrumbs for this document, suitable for rendering in a template."""
        crumbs = [
            BreadCrumb(_("Home"), reverse("home_page")),
        ]
        return crumbs


class JudgmentDecorator(DocumentDecorator):
    """Judgment decorators are used to add extra functionality to judgments."""

    def apply_labels(self, document):
        """Apply labels to this judgment based on its properties."""
        from peachjam.models import Label

        # label showing that a judgment is cited/reported in law reports, hence "more important"
        label, _ = Label.objects.get_or_create(
            code="reported",
            defaults={"name": "Reported", "code": "reported", "level": "success"},
        )

        labels = list(document.labels.all())

        # if the judgment has alternative_names, apply the "reported" label
        if document.alternative_names.exists():
            if label not in labels:
                document.labels.add(label.pk)
        # if the judgment has no alternative_names, remove the "reported" label
        elif label in labels:
            document.labels.remove(label.pk)

        super().apply_labels(document)

    def get_breadcrumbs(self, document):
        crumbs = super().get_breadcrumbs(document)
        crumbs.append(BreadCrumb(name=_("Judgments"), url=reverse("judgment_list")))
        if document.court.court_class:
            if document.court.court_class.show_listing_page:
                crumbs.append(
                    BreadCrumb(
                        name=document.court.court_class.name,
                        url=document.court.court_class.get_absolute_url(),
                    )
                )
        if document.court:
            crumbs.append(
                BreadCrumb(
                    name=document.court.name,
                    url=document.court.get_absolute_url(),
                )
            )
        if document.registry:
            crumbs.append(
                BreadCrumb(
                    name=document.registry.name,
                    url=document.registry.get_absolute_url(),
                )
            )
        crumbs.append(
            BreadCrumb(
                name=str(document.date.year),
                url=reverse(
                    "court_year", args=[document.court.code, document.date.year]
                ),
            )
        )
        return crumbs


class LegislationDecorator(DocumentDecorator):
    def apply_labels(self, document):
        from peachjam.models import Label

        labels = list(document.labels.all())

        # label to indicate that this legislation is repealed
        repealed_label, _ = Label.objects.get_or_create(
            code="repealed",
            defaults={"name": "Repealed", "code": "repealed", "level": "danger"},
        )
        revoked_label, _ = Label.objects.get_or_create(
            code="revoked",
            defaults={"name": "Revoked", "code": "revoked", "level": "danger"},
        )
        withdrawn_label, _ = Label.objects.get_or_create(
            code="withdrawn",
            defaults={"name": "Withdrawn", "code": "withdrawn", "level": "danger"},
        )
        lapsed_label, _ = Label.objects.get_or_create(
            code="lapsed",
            defaults={"name": "Lapsed", "code": "lapsed", "level": "danger"},
        )
        retired_label, _ = Label.objects.get_or_create(
            code="retired",
            defaults={"name": "Retired", "code": "retired", "level": "danger"},
        )
        expired_label, _ = Label.objects.get_or_create(
            code="expired",
            defaults={"name": "Expired", "code": "expired", "level": "danger"},
        )
        replaced_label, _ = Label.objects.get_or_create(
            code="replaced",
            defaults={"name": "Replaced", "code": "replaced", "level": "danger"},
        )
        repealed_labels = [
            repealed_label,
            revoked_label,
            withdrawn_label,
            lapsed_label,
            retired_label,
            expired_label,
            replaced_label,
        ]
        uncommenced_label, _ = Label.objects.get_or_create(
            code="uncommenced",
            defaults={
                "name": "Uncommenced",
                "level": "danger",
            },
        )

        # apply label if repealed
        existing_repeal_labels = document.labels.filter(
            pk__in=[label.pk for label in repealed_labels]
        )
        if document.repealed:
            verb = document.metadata_json["repeal"].get("verb", "repealed")
            # if the verb isn't in repealed_labels, we need to add it for translations (and under Adapter.predicates)
            assert verb in [label.code for label in repealed_labels]
            apply_label = Label.objects.get(code=verb)
            # apply the right label, and remove any other repeal-like labels
            for label in existing_repeal_labels:
                if label != apply_label:
                    document.labels.remove(label.pk)
            if apply_label not in labels:
                document.labels.add(apply_label.pk)
        else:
            for remove_label in existing_repeal_labels:
                # not repealed, remove label
                document.labels.remove(remove_label.pk)

        # apply label if not commenced
        if not document.commenced:
            if uncommenced_label not in labels:
                document.labels.add(uncommenced_label.pk)
        elif uncommenced_label in labels:
            document.labels.remove(uncommenced_label.pk)

        super().apply_labels(document)

    def get_breadcrumbs(self, document):
        crumbs = super().get_breadcrumbs(document)
        crumbs.append(BreadCrumb(_("Legislation"), reverse("legislation_list")))
        return crumbs


class GazetteDecorator(DocumentDecorator):
    def get_breadcrumbs(self, document):
        breadcrumbs = super().get_breadcrumbs(document)
        breadcrumbs.append(
            BreadCrumb(
                _("Gazettes"),
                reverse("gazettes"),
            )
        )
        breadcrumbs.append(
            BreadCrumb(
                document.jurisdiction.name,
                reverse(
                    "gazettes_by_locality", args=[document.jurisdiction.pk.lower()]
                ),
            )
        )
        if document.locality:
            breadcrumbs.append(
                BreadCrumb(
                    document.locality.name,
                    reverse(
                        "gazettes_by_locality", args=[document.locality.place_code]
                    ),
                )
            )
            breadcrumbs.append(
                BreadCrumb(
                    str(document.date.year),
                    reverse(
                        "gazettes_by_year",
                        args=[document.locality.place_code, document.date.year],
                    ),
                )
            )
        elif settings.PEACHJAM["MULTIPLE_JURISDICTIONS"]:
            breadcrumbs.append(
                BreadCrumb(
                    str(document.date.year),
                    reverse(
                        "gazettes_by_year",
                        args=[document.jurisdiction.pk.lower(), document.date.year],
                    ),
                )
            )
        else:
            breadcrumbs.append(
                BreadCrumb(
                    str(document.date.year),
                    reverse("gazettes_by_year", args=[document.date.year]),
                )
            )
        return breadcrumbs


class GenericDocumentDecorator(DocumentDecorator):
    def get_breadcrumbs(self, document):
        crumbs = super().get_breadcrumbs(document)
        if document.nature:
            crumbs.append(
                BreadCrumb(
                    document.nature.name,
                    reverse("document_nature_list", args=[document.nature.code]),
                )
            )
        return crumbs


class CauseListDecorator(DocumentDecorator):
    def get_breadcrumbs(self, document):
        crumbs = super().get_breadcrumbs(document)
        crumbs.append(BreadCrumb(_("Cause Lists"), reverse("causelist_list")))
        if document.court.court_class:
            if document.court.court_class.show_listing_page:
                crumbs.append(
                    BreadCrumb(
                        document.court.court_class.name,
                        reverse(
                            "causelist_court_class",
                            args=[document.court.court_class.slug],
                        ),
                    )
                )
        if document.court:
            crumbs.append(
                BreadCrumb(
                    document.court.name,
                    reverse("causelist_court", args=[document.court.code]),
                )
            )
        if document.registry:
            crumbs.append(
                BreadCrumb(
                    document.registry.name,
                    reverse(
                        "causelist_court_registry",
                        args=[document.court.code, document.registry.code],
                    ),
                )
            )
        crumbs.append(
            BreadCrumb(
                str(document.date.year),
                reverse(
                    "causelist_court_year",
                    args=[document.court.code, document.date.year],
                ),
            )
        )
        return crumbs


class BookDecorator(DocumentDecorator):
    def get_breadcrumbs(self, document):
        crumbs = super().get_breadcrumbs(document)
        crumbs.append(BreadCrumb(_("Books"), reverse("book_list")))
        return crumbs


class JournalDecorator(DocumentDecorator):
    def get_breadcrumbs(self, document):
        crumbs = super().get_breadcrumbs(document)
        crumbs.append(BreadCrumb(_("Journals"), reverse("journal_list")))
        return crumbs


class BillDecorator(DocumentDecorator):
    def get_breadcrumbs(self, document):
        crumbs = super().get_breadcrumbs(document)
        crumbs.append(BreadCrumb(_("Bills"), reverse("bill_list")))
        return crumbs
