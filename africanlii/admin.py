from countries_plus.models import Country
from django.contrib import admin

from africanlii.models import Ratification, RatificationCountry


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
