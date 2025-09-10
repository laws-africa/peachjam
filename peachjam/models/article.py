import os
import uuid

from django.contrib.auth import get_user_model
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from languages_plus.models import Language


def file_location(instance, filename):
    filename = os.path.basename(filename)
    return f"{instance.SAVE_FOLDER}/{instance.pk}/{filename}"


class Article(models.Model):
    SAVE_FOLDER = "articles"
    doc_type = "article"

    date = models.DateField(_("date"), null=False, blank=False)
    title = models.CharField(_("title"), max_length=1024, null=False, blank=False)
    body = models.TextField(_("body"))
    author = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="articles",
        verbose_name=_("author"),
    )
    image = models.ImageField(
        _("image"), upload_to=file_location, blank=True, null=True
    )
    summary = models.TextField(_("summary"), null=True, blank=True)
    slug = models.SlugField(_("slug"), max_length=1024, unique=True)
    published = models.BooleanField(_("published"), default=False)
    topics = models.ManyToManyField(
        "peachjam.Taxonomy", verbose_name=_("topics"), blank=True
    )
    featured = models.BooleanField(
        _("featured"),
        default=False,
        help_text=_("Featured articles will be displayed on the homepage."),
    )

    class Meta:
        verbose_name = _("article")
        verbose_name_plural = _("articles")
        ordering = ("-date",)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse(
            "article_detail",
            kwargs={
                "date": self.date.strftime("%Y-%m-%d"),
                "author": self.author.username,
                "slug": self.slug,
            },
        )

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)

        # save article first to get pk for image folder
        if not self.pk:
            saved_image = self.image
            self.image = None
            super().save(*args, **kwargs)
            self.image = saved_image

        return super().save(*args, **kwargs)

    @classmethod
    def get_article_tags_root(cls):
        from peachjam.models import Taxonomy

        root = Taxonomy.objects.filter(name_en__iexact="Article tags").first()
        if not root:
            root = Taxonomy.add_root(name_en="Article tags")
        return root


class UserProfile(models.Model):
    SAVE_FOLDER = "user_profiles"

    user = models.OneToOneField(
        get_user_model(), on_delete=models.CASCADE, verbose_name=_("user")
    )
    photo = models.ImageField(
        _("photo"), upload_to=file_location, blank=True, null=True
    )
    profile_description = models.TextField(_("profile description"))
    tracking_id = models.UUIDField(_("tracking id"), default=uuid.uuid4, editable=False)

    preferred_language = models.ForeignKey(
        Language,
        on_delete=models.PROTECT,
        default="en",
        related_name="+",
        verbose_name=_("preferred language"),
    )

    class Meta:
        verbose_name = _("user profile")
        verbose_name_plural = _("user profiles")

    @property
    def tracking_id_str(self):
        return str(self.tracking_id)

    def is_primary_email_verified(self):
        return self.user.emailaddress_set.filter(
            verified=True, email=self.user.email
        ).exists()

    def __str__(self):
        return f"{self.user.username}"


@receiver(post_save, sender=get_user_model())
def user_saved(sender, instance, created, **kwargs):
    if created:
        # ensure a user profile exists
        UserProfile.objects.get_or_create(user=instance)
