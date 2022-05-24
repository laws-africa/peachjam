from django.db import models


class Predicate(models.Model):
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=50, unique=True)
    verb = models.CharField(max_length=100)
    reverse_verb = models.CharField(
        max_length=100, help_text="Reversed verbal form of the relationship"
    )

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return f"{self.verb} ({self.name})"


class RelationshipQuerySet(models.QuerySet):
    def load_object_documents(self):
        """Load the object documents for this queryset, transforming it into a normal list."""
        from peachjam.models import CoreDocument

        rels = list(self)
        # TODO: handle duplicate expressions by choosing an appropriate language?
        docs = CoreDocument.objects.filter(
            work_frbr_uri__in={r.object_work_frbr_uri for r in rels}
        )
        docs = {d.work_frbr_uri: d for d in docs}

        for rel in rels:
            rel.object_document = docs.get(rel.object_work_frbr_uri)

        return rels

    def load_subject_documents(self):
        """Load the subject documents for this queryset, transforming it into a normal list."""
        from peachjam.models import CoreDocument

        rels = list(self)
        # TODO: handle duplicate expressions by choosing an appropriate language?
        docs = CoreDocument.objects.filter(
            work_frbr_uri__in={r.subject_work_frbr_uri for r in rels}
        )
        docs = {d.work_frbr_uri: d for d in docs}

        for rel in rels:
            rel.subject_document = docs.get(rel.subject_work_frbr_uri)

        return rels


class Relationship(models.Model):
    subject_work_frbr_uri = models.CharField(max_length=1024)
    subject_target_id = models.CharField(max_length=1024)

    object_work_frbr_uri = models.CharField(max_length=1024)
    object_target_id = models.CharField(max_length=1024)

    predicate = models.ForeignKey(Predicate, on_delete=models.PROTECT)

    class Meta:
        unique_together = (
            "subject_work_frbr_uri",
            "subject_target_id",
            "object_work_frbr_uri",
            "object_target_id",
            "predicate",
        )

    objects = RelationshipQuerySet.as_manager()

    @classmethod
    def for_subject_document(cls, doc):
        return cls.objects.filter(subject_work_frbr_uri=doc.work_frbr_uri)

    @classmethod
    def for_object_document(cls, doc):
        return cls.objects.filter(object_work_frbr_uri=doc.work_frbr_uri)
