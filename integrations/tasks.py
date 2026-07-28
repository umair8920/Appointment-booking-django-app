"""Celery tasks for Cliniko pull/push sync (Docs/06, 07)."""

from __future__ import annotations

import logging
from typing import Any

from celery import shared_task
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from appointments.models import Appointment, AvailabilitySlot
from integrations.base import get_pms_adapter
from integrations.models import PMSSyncLog
from practitioners.models import PractitionerProfile

logger = logging.getLogger(__name__)
User = get_user_model()
PMS_NAME = "cliniko"


def _start_log(sync_type: str) -> PMSSyncLog:
    return PMSSyncLog.objects.create(
        pms_name=PMS_NAME,
        sync_type=sync_type,
        status=PMSSyncLog.Status.SUCCESS,
        started_at=timezone.now(),
    )


def _finish_log(log: PMSSyncLog, *, ok: bool, error: str = "") -> None:
    log.status = PMSSyncLog.Status.SUCCESS if ok else PMSSyncLog.Status.FAILED
    log.finished_at = timezone.now()
    log.error_message = error
    log.save(update_fields=["status", "finished_at", "error_message"])


@shared_task(name="integrations.tasks.sync_cliniko_practitioners")
def sync_cliniko_practitioners() -> dict[str, Any]:
    """Pull practitioners from Cliniko and upsert PractitionerProfile (Docs/07)."""
    log = _start_log(PMSSyncLog.SyncType.PULL_PRACTITIONERS)
    try:
        adapter = get_pms_adapter()
        practitioners = adapter.fetch_practitioners()
        created = updated = 0
        for item in practitioners:
            _, was_created = _upsert_practitioner(item)
            if was_created:
                created += 1
            else:
                updated += 1
        _finish_log(log, ok=True)
        return {"created": created, "updated": updated, "total": len(practitioners)}
    except Exception as exc:
        logger.exception("sync_cliniko_practitioners failed")
        _finish_log(log, ok=False, error=str(exc))
        raise


@shared_task(name="integrations.tasks.sync_cliniko_availability")
def sync_cliniko_availability() -> dict[str, Any]:
    """Pull availability for Cliniko-linked practitioners (Docs/07)."""
    log = _start_log(PMSSyncLog.SyncType.PULL_AVAILABILITY)
    try:
        adapter = get_pms_adapter()
        linked = PractitionerProfile.objects.exclude(
            cliniko_practitioner_id__isnull=True
        ).exclude(cliniko_practitioner_id="")
        slots_upserted = 0
        for profile in linked:
            slots = adapter.fetch_availability(profile.cliniko_practitioner_id)
            for slot in slots:
                obj, created = AvailabilitySlot.objects.get_or_create(
                    practitioner=profile,
                    start_time=slot.start_time,
                    defaults={
                        "end_time": slot.end_time,
                        "source": AvailabilitySlot.Source.CLINIKO,
                        "is_booked": False,
                    },
                )
                if created:
                    slots_upserted += 1
                elif not obj.is_booked:
                    obj.end_time = slot.end_time
                    obj.source = AvailabilitySlot.Source.CLINIKO
                    obj.save(update_fields=["end_time", "source"])
        _finish_log(log, ok=True)
        return {"practitioners": linked.count(), "slots_created": slots_upserted}
    except Exception as exc:
        logger.exception("sync_cliniko_availability failed")
        _finish_log(log, ok=False, error=str(exc))
        raise


@shared_task(name="integrations.tasks.push_appointment_to_cliniko")
def push_appointment_to_cliniko(appointment_id: int) -> str | None:
    """Push confirmed appointment to Cliniko; store external id (Docs/07)."""
    log = _start_log(PMSSyncLog.SyncType.PUSH_APPOINTMENT)
    try:
        appointment = Appointment.objects.select_related(
            "practitioner", "patient__user", "slot"
        ).get(pk=appointment_id)

        if appointment.cliniko_appointment_id:
            _finish_log(log, ok=True)
            return appointment.cliniko_appointment_id

        adapter = get_pms_adapter()
        external_id = adapter.push_appointment(appointment)
        appointment.cliniko_appointment_id = external_id
        appointment.save(update_fields=["cliniko_appointment_id"])
        _finish_log(log, ok=True)
        return external_id
    except Exception as exc:
        logger.exception("push_appointment_to_cliniko failed")
        _finish_log(log, ok=False, error=str(exc))
        raise


@transaction.atomic
def _upsert_practitioner(item) -> tuple[PractitionerProfile, bool]:
    existing = PractitionerProfile.objects.filter(
        cliniko_practitioner_id=item.external_id
    ).select_related("user").first()
    if existing:
        if not existing.specialization:
            existing.specialization = item.display_name
            existing.save(update_fields=["specialization"])
        return existing, False

    email = f"cliniko.{item.external_id}@synced.local"
    user, user_created = User.objects.get_or_create(
        email=email,
        defaults={
            "role": User.Role.PRACTITIONER,
            "is_profile_complete": True,
            "first_name": (item.first_name or "")[:150],
            "last_name": (item.last_name or "")[:150],
        },
    )
    if user_created or not user.has_usable_password():
        user.set_unusable_password()
        user.role = User.Role.PRACTITIONER
        user.is_profile_complete = True
        user.save()

    # Signal may have already created an empty PractitionerProfile.
    profile, _ = PractitionerProfile.objects.get_or_create(user=user)
    was_new_link = not profile.cliniko_practitioner_id
    profile.cliniko_practitioner_id = item.external_id
    if not profile.specialization:
        profile.specialization = item.display_name
    profile.save()
    return profile, was_new_link
