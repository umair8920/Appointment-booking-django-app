"""ClinikoAdapter(PMSAdapter) — Docs/07."""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from appointments.models import Appointment
from integrations.base import NormalizedPractitioner, NormalizedSlot, PMSAdapter
from integrations.cliniko import mappers
from integrations.cliniko.client import ClinikoClient


class ClinikoAdapter(PMSAdapter):
    def __init__(self, client: ClinikoClient | None = None) -> None:
        self.client = client or ClinikoClient()

    def fetch_practitioners(self) -> list[NormalizedPractitioner]:
        raw_list = self.client.list_all("practitioners", "practitioners")
        return [mappers.map_practitioner(raw) for raw in raw_list]

    def fetch_availability(self, external_practitioner_id: str) -> list[NormalizedSlot]:
        business_id = self._business_id()
        appointment_type_id = self._appointment_type_id()
        duration = self._appointment_type_duration_minutes(appointment_type_id)

        # Cliniko available_times window is max 7 days.
        start_day = timezone.localdate()
        end_day = start_day + timedelta(days=6)
        path = (
            f"businesses/{business_id}/practitioners/{external_practitioner_id}/"
            f"appointment_types/{appointment_type_id}/available_times"
        )
        try:
            raw_times = self.client.list_all(
                "available_times",
                path,
                params={"from": start_day.isoformat(), "to": end_day.isoformat()},
            )
        except Exception as exc:
            # Cliniko returns 404 when business/practitioner/type is not enabled
            # for online bookings (common on fresh trial accounts).
            message = str(exc)
            if "404" in message:
                return []
            raise
        slots: list[NormalizedSlot] = []
        for raw in raw_times:
            mapped = mappers.map_available_time(
                raw,
                external_practitioner_id=external_practitioner_id,
                duration_minutes=duration,
            )
            if mapped:
                slots.append(mapped)
        return slots

    def push_appointment(self, appointment: Appointment) -> str:
        practitioner = appointment.practitioner
        if not practitioner.cliniko_practitioner_id:
            raise ValueError("Practitioner has no cliniko_practitioner_id; cannot push.")

        patient_id = self._ensure_cliniko_patient(appointment)
        payload = mappers.map_appointment_create_payload(
            cliniko_practitioner_id=practitioner.cliniko_practitioner_id,
            cliniko_patient_id=patient_id,
            starts_at=appointment.slot.start_time,
            ends_at=appointment.slot.end_time,
            appointment_type_id=self._appointment_type_id_optional(),
            business_id=self._business_id(),
        )
        created = self.client.post("individual_appointments", payload)
        return mappers.map_created_appointment_id(created)

    def cancel_appointment(self, appointment: Appointment) -> None:
        external_id = appointment.cliniko_appointment_id
        if not external_id:
            return
        self.client.delete(f"individual_appointments/{external_id}")

    def _business_id(self) -> str:
        configured = getattr(settings, "CLINIKO_BUSINESS_ID", "") or ""
        if configured:
            return str(configured)
        businesses = self.client.list_all("businesses", "businesses")
        if not businesses:
            raise ValueError("No Cliniko businesses found; set CLINIKO_BUSINESS_ID.")
        return str(businesses[0]["id"])

    def _appointment_type_id(self) -> str:
        configured = getattr(settings, "CLINIKO_APPOINTMENT_TYPE_ID", "") or ""
        if configured:
            return str(configured)
        types = self.client.list_all("appointment_types", "appointment_types")
        if not types:
            raise ValueError(
                "No Cliniko appointment types found; set CLINIKO_APPOINTMENT_TYPE_ID."
            )
        return str(types[0]["id"])

    def _appointment_type_id_optional(self) -> str | None:
        try:
            return self._appointment_type_id()
        except ValueError:
            return None

    def _appointment_type_duration_minutes(self, appointment_type_id: str) -> int:
        raw = self.client.get(f"appointment_types/{appointment_type_id}")
        duration = raw.get("duration_in_minutes") or raw.get("duration")
        try:
            return int(duration)
        except (TypeError, ValueError):
            return 30

    def _ensure_cliniko_patient(self, appointment: Appointment) -> str:
        """
        Find or create a Cliniko patient for this booking.

        Does not add model fields (Docs/03) — lookup by email, create if missing.
        """
        patient = appointment.patient
        email = patient.user.email
        found = self.client.get(
            "patients",
            params={"q[]": f"email:={email}", "per_page": 5},
        )
        for row in found.get("patients") or []:
            if (row.get("email") or "").lower() == email.lower():
                return str(row["id"])

        created = self.client.post(
            "patients",
            {
                "first_name": patient.user.first_name or "Patient",
                "last_name": patient.user.last_name or str(patient.user_id),
                "email": email,
            },
        )
        return str(created["id"])
