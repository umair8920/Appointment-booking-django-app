"""Cliniko JSON -> NormalizedPractitioner / NormalizedSlot (Docs/07).

This is the only module allowed to know Cliniko response field names.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from django.utils.dateparse import parse_datetime
from django.utils import timezone

from integrations.base import NormalizedPractitioner, NormalizedSlot


def map_practitioner(raw: dict[str, Any]) -> NormalizedPractitioner:
    first = (raw.get("first_name") or "").strip()
    last = (raw.get("last_name") or "").strip()
    display = f"{first} {last}".strip() or f"Practitioner {raw.get('id')}"
    return NormalizedPractitioner(
        external_id=str(raw["id"]),
        first_name=first,
        last_name=last,
        display_name=display,
    )


def map_available_time(
    raw: dict[str, Any],
    *,
    external_practitioner_id: str,
    duration_minutes: int,
) -> NormalizedSlot | None:
    start_raw = raw.get("appointment_start")
    if not start_raw:
        return None
    start = parse_datetime(start_raw)
    if start is None:
        return None
    if timezone.is_naive(start):
        start = timezone.make_aware(start, timezone.utc)
    end = start + timedelta(minutes=duration_minutes)
    return NormalizedSlot(
        external_practitioner_id=external_practitioner_id,
        start_time=start,
        end_time=end,
    )


def map_appointment_create_payload(
    *,
    cliniko_practitioner_id: str,
    cliniko_patient_id: str,
    starts_at: datetime,
    ends_at: datetime,
    appointment_type_id: str | None,
    business_id: str | None = None,
) -> dict[str, Any]:
    # Cliniko individual_appointments expects starts_at / ends_at (+ business_id).
    payload: dict[str, Any] = {
        "practitioner_id": str(cliniko_practitioner_id),
        "patient_id": str(cliniko_patient_id),
        "starts_at": starts_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ends_at": ends_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if appointment_type_id:
        payload["appointment_type_id"] = str(appointment_type_id)
    if business_id:
        payload["business_id"] = str(business_id)
    return payload


def map_created_appointment_id(raw: dict[str, Any]) -> str:
    return str(raw["id"])
