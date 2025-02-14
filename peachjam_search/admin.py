from background_task.admin import TaskAdmin
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.timezone import now

from peachjam_search.models import SearchFeedback


@admin.register(SearchFeedback)
class SearchFeedbackAdmin(admin.ModelAdmin):
    fields = ("search_trace_link", "feedback", "name", "email", "user")
    readonly_fields = ("search_trace_link", "feedback", "name", "email", "user")
    date_hierarchy = "created_at"

    def search_trace_link(self, instance):
        if instance.search_trace is not None:
            return format_html(
                '<a href="{}">{}</a>',
                reverse("search:search_trace", args=[instance.search_trace.id]),
                instance.search_trace.id,
            )


def run_now(modeladmin, request, queryset):
    for obj in queryset:
        obj.run_at = now()
        obj.save()


run_now.short_description = "Set run time to now"


TaskAdmin.actions.append(run_now)
