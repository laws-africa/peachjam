from countries_plus.models import Country
from django.contrib import admin

from africanlii.models import Ratification, RatificationCountry
from peachjam.admin import EntityProfileInline
from peachjam.models import AfricanUnionOrgan, MemberState, RegionalEconomicCommunity


class RatificationCountryAdmin(admin.TabularInline):
    model = RatificationCountry
    extra = 1

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "country":
            kwargs["queryset"] = Country.objects.filter(continent="AF")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Ratification)
class RatificationAdmin(admin.ModelAdmin):
    inlines = (RatificationCountryAdmin,)


@admin.register(AfricanUnionOrgan)
class AfricanUnionOrganAdmin(admin.ModelAdmin):
    inlines = [EntityProfileInline]


@admin.register(RegionalEconomicCommunity)
class RegionalEconomicCommunityAdmin(admin.ModelAdmin):
    inlines = [EntityProfileInline]


@admin.register(MemberState)
class MemberStateAdmin(admin.ModelAdmin):
    inlines = [EntityProfileInline]
