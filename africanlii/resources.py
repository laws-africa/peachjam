from countries_plus.models import Country
from import_export import fields, resources, widgets

from africanlii.models import Ratification, RatificationCountry
from peachjam.models import Work


class RatificationField(widgets.ForeignKeyWidget):
    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            raise ValueError("work frbr_uri is required")
        work = Work.objects.filter(frbr_uri=value).first()
        if not work:
            raise ValueError(f'work with frbr_uri "{value}" not found')
        ratification = Ratification.objects.update_or_create(
            work=work,
            defaults={
                "source_url": row.get("source_url"),
                "last_updated": row.get("last_updated"),
            },
        )[0]
        return ratification


class CountryField(widgets.ForeignKeyWidget):
    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            raise ValueError("country code is required")
        country = Country.objects.filter(iso=value.upper()).first()
        if not country:
            raise ValueError(f'country with iso "{value}" not found')
        return country


class RatificationResource(resources.ModelResource):
    work = fields.Field(
        column_name="work",
        attribute="ratification",
        widget=RatificationField(Ratification, field="work__frbr_uri"),
    )
    country = fields.Field(
        attribute="country",
        column_name="country",
        widget=CountryField(Country, field="name"),
    )
    ratification_date = fields.Field(
        attribute="ratification_date",
        column_name="ratification_date",
        widget=widgets.DateWidget(),
    )
    deposit_date = fields.Field(
        attribute="deposit_date",
        column_name="deposit_date",
        widget=widgets.DateWidget(),
    )
    signature_date = fields.Field(
        attribute="signature_date",
        column_name="signature_date",
        widget=widgets.DateWidget(),
    )
    source_url = fields.Field(
        attribute="source_url", column_name="source_url", widget=widgets.CharWidget()
    )
    last_updated = fields.Field(
        attribute="last_updated",
        column_name="last_updated",
        widget=widgets.DateWidget(),
    )

    class Meta:
        model = RatificationCountry
        exclude = ("id", "ratification")
        import_id_fields = (
            "work",
            "country",
        )
