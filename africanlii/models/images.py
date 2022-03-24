from django.db import models

class ImageSet(models.Model):
  def default_image(self):
    return self.images.first()

class Image(models.Model):
  image_set = models.ForeignKey(ImageSet, on_delete=models.CASCADE)
  image = models.ImageField(upload_to='media/images')
  caption = models.CharField(max_length=255, null=True, blank=True)
  description = models.TextField(null=True, blank=True)
  created_at = models.DateTimeField(auto_now_add=True)
  updated_at = models.DateTimeField(auto_now=True)
