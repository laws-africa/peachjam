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
        uncommenced_label, _ = Label.objects.get_or_create(
            code="uncommenced",
            defaults={
                "name": "Uncommenced",
                "level": "danger",
            },
        )

        # apply label if repealed
        if document.repealed:
            if repealed_label not in labels:
                document.labels.add(repealed_label.pk)
        elif repealed_label in labels:
            # not repealed, remove label
            document.labels.remove(repealed_label.pk)

        # apply label if not commenced
        if not document.commenced:
            if uncommenced_label not in labels:
                document.labels.add(uncommenced_label.pk)
        elif uncommenced_label in labels:
            document.labels.remove(uncommenced_label.pk)

        super().apply_labels(document)
