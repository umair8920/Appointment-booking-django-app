from django.contrib import admin

from .models import PMSSyncLog


@admin.register(PMSSyncLog)
class PMSSyncLogAdmin(admin.ModelAdmin):
    list_display = ("id", "pms_name", "sync_type", "status", "started_at", "finished_at")
    list_filter = ("pms_name", "sync_type", "status")
    search_fields = ("error_message",)
