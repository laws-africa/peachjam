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
