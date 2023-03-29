from background_task.admin import TaskAdmin
from django.utils.timezone import now


def run_now(modeladmin, request, queryset):
    for obj in queryset:
        obj.run_at = now()
        obj.save()


run_now.short_description = "Set run time to now"


TaskAdmin.actions.append(run_now)
