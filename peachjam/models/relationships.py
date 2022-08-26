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


class Relationship(models.Model):
    subject_work = models.ForeignKey(
        "peachjam.Work", null=False, on_delete=models.CASCADE, related_name="+"
    )
    subject_target_id = models.CharField(max_length=1024, null=True, blank=True)

    object_work = models.ForeignKey(
        "peachjam.Work", null=False, on_delete=models.CASCADE, related_name="+"
    )
    object_target_id = models.CharField(max_length=1024, null=True, blank=True)

    predicate = models.ForeignKey(Predicate, on_delete=models.PROTECT)

    class Meta:
        unique_together = (
            "subject_work",
            "subject_target_id",
            "object_work",
            "object_target_id",
            "predicate",
        )

    def subject_documents(self):
        return self.subject_work.documents.order_by("-date")

    def object_documents(self):
        return self.object_work.documents.order_by("-date")

    def subject_document(self):
        # TODO: better way of doing this for the view? choose the right language?
        documents = self.subject_documents()
        if documents.count() > 0:
            return documents[0]
        else:
            return None

    def object_document(self):
        # TODO: better way of doing this for the view? choose the right language?
        documents = self.object_documents()
        if documents.count() > 0:
            return documents[0]
        else:
            return None

    @classmethod
    def for_subject_document(cls, doc):
        return cls.objects.filter(subject_work=doc.work)

    @classmethod
    def for_object_document(cls, doc):
        return cls.objects.filter(object_work=doc.work)
