from django.contrib import admin

from africanlii.models import (
    AfricanUnionInstitution,
    AfricanUnionOrgan,
    MemberState,
    RegionalEconomicCommunity,
)
from peachjam.admin import EntityProfileInline


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
