"""Appointment / availability serializers — Docs/03, 04."""

from rest_framework import serializers

from appointments.models import Appointment, AvailabilitySlot


class AvailabilitySlotSerializer(serializers.ModelSerializer):
    """Open-slot shape from Docs/04 example (no `source` / PMS keys)."""

    class Meta:
        model = AvailabilitySlot
        fields = ("id", "start_time", "end_time", "is_booked")
        read_only_fields = fields


class AppointmentSerializer(serializers.ModelSerializer):
    slot = AvailabilitySlotSerializer(read_only=True)
    practitioner_id = serializers.IntegerField(source="practitioner.id", read_only=True)
    patient_id = serializers.IntegerField(source="patient.id", read_only=True)

    class Meta:
        model = Appointment
        fields = (
            "id",
            "patient_id",
            "practitioner_id",
            "slot",
            "status",
            "created_at",
        )
        read_only_fields = fields


class BookAppointmentSerializer(serializers.Serializer):
    slot_id = serializers.IntegerField()
