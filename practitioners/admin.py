from django.contrib import admin

from .models import PractitionerProfile


@admin.register(PractitionerProfile)
class PractitionerProfileAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "specialization",
        "consultation_fee",
        "cliniko_practitioner_id",
    )
    search_fields = ("user__email", "specialization", "license_number", "cliniko_practitioner_id")
    raw_id_fields = ("user",)
