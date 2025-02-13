from background_task.admin import TaskAdmin
from django.contrib import admin
from django.utils.timezone import now

from peachjam_search.models import SearchFeedback

admin.site.register(SearchFeedback)


def run_now(modeladmin, request, queryset):
    for obj in queryset:
        obj.run_at = now()
        obj.save()


run_now.short_description = "Set run time to now"


TaskAdmin.actions.append(run_now)
