from django.contrib import admin

from .models import PatientProfile


@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "phone_number", "date_of_birth")
    search_fields = ("user__email", "phone_number")
    raw_id_fields = ("user",)
