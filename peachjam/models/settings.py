from django.db import models
from django.utils.translation import gettext_lazy as _


class SingletonModel(models.Model):
    class Meta:
        abstract = True

    def delete(self, *args, **kwargs):
        pass

    def save(self, *args, **kwargs):
        self.pk = 1
        super(SingletonModel, self).save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj


class PeachJamSettings(SingletonModel):
    default_document_language = models.ForeignKey(
        "languages_plus.Language",
        related_name="+",
        null=True,
        on_delete=models.SET_NULL,
        verbose_name=_("default document language"),
    )
    document_languages = models.ManyToManyField(
        "languages_plus.Language",
        related_name="+",
        blank=True,
        verbose_name=_("document languages"),
    )
    default_document_jurisdiction = models.ForeignKey(
        "countries_plus.Country",
        related_name="+",
        null=True,
        on_delete=models.SET_NULL,
        verbose_name=_("default document jurisdiction"),
    )
    document_jurisdictions = models.ManyToManyField(
        "countries_plus.Country",
        related_name="+",
        blank=True,
        verbose_name=_("document jurisdictions"),
    )
    subleg_label = models.CharField(
        verbose_name=_("subsidiary legislation label"),
        max_length=1024,
        default="Subsidiary legislation",
    )
    google_analytics_id = models.CharField(
        verbose_name=_("google analytics id"),
        max_length=1024,
        null=True,
        blank=True,
        help_text=_("Enter one or more Google Analytics IDs separated by spaces."),
    )
    pagerank_boost_value = models.FloatField(
        verbose_name=_("pagerank boost value"), null=True, blank=True
    )
    pagerank_pivot_value = models.FloatField(
        verbose_name=_("pagerank pivot value"), null=True, blank=True
    )
    allowed_login_domains = models.CharField(
        verbose_name=_("allowed login domains"), max_length=1024, null=True, blank=True
    )
    allow_social_logins = models.BooleanField(
        verbose_name=_("allow social logins"),
        default=False,
        help_text=_("Allow signups via social accounts"),
    )
    allow_signups = models.BooleanField(
        verbose_name=_("allow signups"),
        default=True,
        help_text=_("Allow users to create accounts"),
    )

    metabase_dashboard_link = models.URLField(
        verbose_name=_("metabase dashboard link"), null=True, blank=True
    )

    mailchimp_form_url = models.URLField(
        verbose_name=_("mailchimp form url"), null=True, blank=True
    )
    twitter_link = models.URLField(
        verbose_name=_("twitter link"), null=True, blank=True
    )
    facebook_link = models.URLField(
        verbose_name=_("facebook link"), null=True, blank=True
    )
    linkedin_link = models.URLField(
        verbose_name=_("linkedin link"), null=True, blank=True
    )
    youtube_link = models.URLField(
        verbose_name=_("youtube link"), null=True, blank=True
    )
    contact_form_url = models.URLField(
        verbose_name=_("contact form URL"), null=True, blank=True
    )
    re_extract_citations = models.BooleanField(
        verbose_name=_("re-extract citations"), default=True
    )
    pocket_law_repo = models.CharField(
        verbose_name=_("Pocket Law repo"), max_length=1024, null=True, blank=True
    )
    editor_help_link = models.URLField(
        _("editor help link"),
        default="https://liieditors.docs.laws.africa/",
        null=True,
        blank=True,
    )
    user_help_link = models.URLField(
        _("user help link"),
        default="https://liiguide.docs.laws.africa/",
        null=True,
        blank=True,
    )
    admin_emails = models.CharField(
        verbose_name=_("admin emails"),
        max_length=1024,
        null=True,
        blank=True,
        help_text=_("Enter one or more email addresses separated by spaces."),
    )
    matomo_domain = models.CharField(
        verbose_name=_("matomo domain"),
        max_length=1024,
        null=True,
        blank=True,
        help_text=_("Matomo domain (e.g. mysite.matomo.cloud)"),
    )
    matomo_site_id = models.CharField(
        verbose_name=_("matomo site ID"),
        max_length=10,
        null=True,
        blank=True,
        help_text=_("Matomo site ID (e.g. 2)"),
    )
    survey_link = models.URLField(
        _("survey link"),
        null=True,
        blank=True,
    )
    allow_save_documents = models.BooleanField(
        verbose_name=_("allow save documents"),
        default=False,
        help_text=_("Allow documents to be saved."),
    )
    allow_save_searches = models.BooleanField(
        verbose_name=_("allow save searches"),
        default=False,
        help_text=_("Allow searches to be saved."),
    )
    show_contact_form = models.BooleanField(
        verbose_name=_("show contact form"),
        default=False,
        help_text=_("Show the contact form."),
    )
    robots_txt = models.TextField(
        null=True, blank=True, help_text=_("Additional robots.txt rules.")
    )
    google_search_engine_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text=_("ID of a Google custom search engine."),
    )

    class Meta:
        verbose_name = verbose_name_plural = _("site settings")

    @property
    def twitter_username(self):
        if self.twitter_link:
            # https://foo.com/bar -> bar
            return "@" + self.twitter_link.split("/", 4)[-1]

    def __str__(self):
        return "Settings"


def pj_settings():
    return PeachJamSettings.load()
