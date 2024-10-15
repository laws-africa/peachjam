from countries_plus.models import Country
from django.contrib import admin

from africanlii.forms import RatificationForm
from africanlii.models import (
    AfricanUnionInstitution,
    AfricanUnionOrgan,
    MemberState,
    RegionalEconomicCommunity,
)
from africanlii.resources import RatificationResource
from peachjam.admin import EntityProfileInline, ImportExportMixin
from peachjam.models import Ratification, RatificationCountry


class RatificationCountryAdmin(admin.TabularInline):
    model = RatificationCountry
    extra = 1

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "country":
            kwargs["queryset"] = Country.objects.filter(continent="AF")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Ratification)
class RatificationAdmin(ImportExportMixin, admin.ModelAdmin):
    inlines = (RatificationCountryAdmin,)
    form = RatificationForm
    resource_class = RatificationResource


@admin.register(AfricanUnionOrgan)
class AfricanUnionOrganAdmin(admin.ModelAdmin):
    inlines = [EntityProfileInline]


@admin.register(AfricanUnionInstitution)
class AfricanUnionInstitutionAdmin(admin.ModelAdmin):
    inlines = [EntityProfileInline]


@admin.register(RegionalEconomicCommunity)
class RegionalEconomicCommunityAdmin(admin.ModelAdmin):
    inlines = [EntityProfileInline]


@admin.register(MemberState)
class MemberStateAdmin(admin.ModelAdmin):
    inlines = [EntityProfileInline]
