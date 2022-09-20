import os

from django.contrib.auth import get_user_model
from django.db import models
from django.utils.text import slugify


def file_location(instance, filename):
    if instance.pk is not None:
        filename = os.path.basename(filename)
        return f"{instance.pk}/{instance.SAVE_FOLDER}/{filename}"
    raise ValueError(
        "Article/UserProfile needs to be saved before the image can be attached"
    )


class Article(models.Model):
    SAVE_FOLDER = "articles"

    date = models.DateField(null=False, blank=False)
    title = models.CharField(max_length=1024, null=False, blank=False)
    body = models.TextField()
    author = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    image = models.ImageField(
        upload_to=file_location, blank=True, null=True
    )  # TODO not mandatory
    summary = models.TextField()
    slug = models.SlugField(max_length=1024, unique=True, editable=False)
    published = models.BooleanField(default=False)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        return super().save(*args, **kwargs)


class UserProfile(models.Model):
    SAVE_FOLDER = "user_profiles"

    user = models.OneToOneField(get_user_model(), on_delete=models.CASCADE)
    photo = models.ImageField(
        upload_to=file_location, blank=True, null=True
    )  # TODO not mandatory
    profile_description = models.TextField()

    def __str__(self):
        return f"{self.user.username}"
