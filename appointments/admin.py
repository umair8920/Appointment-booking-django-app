from django.contrib import admin

from .models import Appointment, AvailabilitySlot


@admin.register(AvailabilitySlot)
class AvailabilitySlotAdmin(admin.ModelAdmin):
    list_display = ("id", "practitioner", "start_time", "end_time", "is_booked", "source")
    list_filter = ("is_booked", "source")
    search_fields = ("practitioner__user__email",)
    raw_id_fields = ("practitioner",)


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("id", "patient", "practitioner", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("patient__user__email", "practitioner__user__email", "cliniko_appointment_id")
    raw_id_fields = ("patient", "practitioner", "slot")
