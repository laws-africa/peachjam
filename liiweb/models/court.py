from django.db import models

from peachjam.models import Author


class CourtClass(models.Model):
    name = models.CharField(max_length=100, null=False, unique=True)
    description = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ("name",)
        verbose_name_plural = "Court classes"

    def __str__(self):
        return self.name


class CourtDetail(models.Model):
    court = models.OneToOneField(Author, on_delete=models.PROTECT)
    court_class = models.ForeignKey(CourtClass, on_delete=models.PROTECT)

    def __str__(self):
        return self.court.name
