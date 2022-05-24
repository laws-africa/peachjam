from collections import defaultdict

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
        Relationship.load_object_documents(self)
        return self

    def load_subject_documents(self):
        """Load the subject documents for this queryset, transforming it into a normal list."""
        Relationship.load_subject_documents(self)
        return self


class Relationship(models.Model):
    subject_work_frbr_uri = models.CharField(max_length=1024)
    subject_target_id = models.CharField(max_length=1024, null=True, blank=True)

    object_work_frbr_uri = models.CharField(max_length=1024)
    object_target_id = models.CharField(max_length=1024, null=True, blank=True)

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

    @classmethod
    def load_object_documents(cls, rels):
        """Load the object documents for these relationships."""
        cls.load_documents(rels, "object")

    @classmethod
    def load_subject_documents(cls, rels):
        """Load the subject documents for these relationships."""
        cls.load_documents(rels, "subject")

    @classmethod
    def load_documents(self, rels, attr):
        from peachjam.models import CoreDocument

        frbr_uri_attr = f"{attr}_work_frbr_uri"
        doc_attr = f"{attr}_documents"

        # index frbr uris to load
        frbr_uris = {getattr(r, frbr_uri_attr) for r in rels}
        docs = defaultdict(list)
        for doc in CoreDocument.objects.filter(work_frbr_uri__in=frbr_uris):
            # index docs by frbr uri
            docs[doc.work_frbr_uri].append(doc)

        # link into relationships
        for rel in rels:
            if not hasattr(rel, doc_attr):
                setattr(rel, doc_attr, [])
            frbr_uri = getattr(rel, frbr_uri_attr)
            getattr(rel, doc_attr).extend(docs.get(frbr_uri, []))
