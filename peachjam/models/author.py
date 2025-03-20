from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _


class Author(models.Model):
    model_label = _("Author")
    model_label_plural = _("Authors")

    name = models.CharField(_("name"), max_length=255, null=False, unique=True)
    code = models.SlugField(_("code"), max_length=255, null=False, unique=True)

    entity_profile = GenericRelation(
        "peachjam.EntityProfile", verbose_name=_("profile")
    )

    # TODO: Have author_types?

    class Meta:
        ordering = ["name"]
        verbose_name = _("author")
        verbose_name_plural = _("authors")

    def __str__(self):
        return f"{self.name}"

    def get_absolute_url(self):
        return reverse("author", kwargs={"code": self.code})
