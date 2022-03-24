from django.db import models


class MatterType(models.Model):
    name = models.CharField(max_length=1024, null=False, blank=False, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Judgment(models.Model):
    """ This model represents judgments.
    """
    title = models.CharField(max_length=1024, null=False, blank=False)
    author = models.ForeignKey('africanlii.Court', on_delete=models.PROTECT, null=False, blank=False)
    date = models.DateField(null=False, blank=False)
    citation = models.CharField(max_length=1024, null=True, blank=True)
    case_number_numeric = models.CharField(max_length=1024, null=True, blank=True)
    case_number_year = models.IntegerField(null=True, blank=True)
    case_number_string = models.CharField(max_length=1024, null=True, blank=True)
    matter_type = models.ForeignKey(MatterType, on_delete=models.PROTECT, null=True, blank=True)
    document_content = models.TextField(null=True, blank=True)
    source_url = models.URLField(max_length=2048, null=True, blank=True)
    source_file = models.FileField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.case_number_string = self.get_case_number_string()
        return super().save(*args, **kwargs)

    def get_case_number_string(self):
        return f'{self.matter_type} {self.case_number_numeric} of {self.case_number_year}'
