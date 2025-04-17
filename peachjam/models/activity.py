from django.contrib.auth.models import User
from django.db import models

from peachjam.models import CoreDocument


class EditActivity(models.Model):
    """Time spent editing a document via the admin area."""

    document = models.ForeignKey(CoreDocument, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    start = models.DateTimeField()
    end = models.DateTimeField()
    seconds = models.IntegerField()
    stage = models.CharField(
        max_length=255,
        choices=(
            ("initial", "initial"),
            ("corrections", "corrections"),
            ("anonymisation", "anonymisation"),
        ),
        default="initial",
    )

    class Meta:
        ordering = ("start",)

    def save(self, *args, **kwargs):
        self.seconds = (self.end - self.start).total_seconds()
        super().save(*args, **kwargs)
