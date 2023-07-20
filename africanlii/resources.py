from countries_plus.models import Country
from import_export import fields, resources, widgets

from africanlii.models import Ratification, RatificationCountry
from peachjam.models import Work
from peachjam.resources import ForeignKeyRequiredWidget


class RatificationResource(resources.ModelResource):
    work = fields.Field(
        column_name="work",
        attribute="work",
        widget=ForeignKeyRequiredWidget(Work, field="frbr_uri"),
    )
    country = fields.Field(column_name="country", widget=widgets.CharWidget)
    ratification_date = fields.Field(
        column_name="ratification_date", widget=widgets.DateWidget
    )
    deposit_date = fields.Field(column_name="deposit_date", widget=widgets.DateWidget)
    signature_date = fields.Field(
        column_name="signature_date", widget=widgets.DateWidget
    )

    class Meta:
        model = Ratification
        exclude = ("id",)
        import_id_fields = ("work",)

    def before_import_row(self, row, row_number=None, **kwargs):
        country_code = row.get("country")
        row["country"] = Country.objects.filter(iso__iexact=country_code).first()
        if not row["country"]:
            raise ValueError(f'country with code "{country_code}" not found')

    def after_import_row(self, row, row_result, row_number=None, **kwargs):
        r = RatificationCountry(
            ratification=Ratification.objects.get(pk=row_result.object_id),
            country=row.get("country"),
            ratification_date=row.get("ratification_date"),
            signature_date=row.get("signature_date"),
            deposit_date=row.get("deposit_date"),
        )
        r.save()
