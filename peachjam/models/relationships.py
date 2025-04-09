from django.db import models
from django.utils.translation import gettext_lazy as _


class Predicate(models.Model):
    name = models.CharField(_("name"), max_length=50, unique=True)
    slug = models.SlugField(_("slug"), max_length=50, unique=True)
    verb = models.CharField(_("verb"), max_length=100)
    reverse_verb = models.CharField(
        _("reverse verb"),
        max_length=100,
        help_text=_("Reversed verbal form of the relationship"),
    )

    class Meta:
        ordering = ("name",)
        verbose_name = _("predicate")
        verbose_name_plural = _("predicates")

    def __str__(self):
        return f"{self.verb} ({self.name})"


class Relationship(models.Model):
    subject_work = models.ForeignKey(
        "peachjam.Work",
        null=False,
        on_delete=models.CASCADE,
        related_name="+",
        verbose_name=_("subject work"),
    )
    subject_target_id = models.CharField(
        _("subject target ID"),
        max_length=1024,
        null=False,
        blank=True,
        default="",
    )
    subject_selectors = models.JSONField(
        verbose_name=_("subject selectors"), null=True, blank=False
    )

    object_work = models.ForeignKey(
        "peachjam.Work",
        null=False,
        on_delete=models.CASCADE,
        related_name="+",
        verbose_name=_("object work"),
    )
    object_target_id = models.CharField(
        _("object target ID"),
        max_length=1024,
        null=False,
        blank=True,
        default="",
    )

    predicate = models.ForeignKey(
        Predicate, on_delete=models.PROTECT, verbose_name=_("predicate")
    )

    class Meta:
        unique_together = (
            "subject_work",
            "subject_target_id",
            "object_work",
            "object_target_id",
            "predicate",
        )
        verbose_name = _("predicate")
        verbose_name_plural = _("predicates")

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
        return (
            cls.objects.filter(subject_work=doc.work)
            .prefetch_related("subject_work", "object_work")
            .select_related("predicate")
        )

    @classmethod
    def for_object_document(cls, doc):
        return (
            cls.objects.filter(object_work=doc.work)
            .prefetch_related("object_work", "subject_work")
            .select_related("predicate")
        )
