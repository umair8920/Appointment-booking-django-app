"""Celery tasks — release_stale_pending_appointments (Docs/06, FR-13)."""

from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from appointments.models import Appointment, AvailabilitySlot

logger = logging.getLogger(__name__)


@shared_task(name="appointments.tasks.release_stale_pending_appointments")
def release_stale_pending_appointments() -> int:
    """
    Cancel appointments still in pending_payment after the configured timeout
    and release their slots (FR-13).
    """
    timeout = getattr(settings, "PENDING_APPOINTMENT_TIMEOUT_MINUTES", 15)
    cutoff = timezone.now() - timedelta(minutes=timeout)

    stale_ids = list(
        Appointment.objects.filter(
            status=Appointment.Status.PENDING_PAYMENT,
            created_at__lt=cutoff,
        ).values_list("id", flat=True)
    )

    released = 0
    for appointment_id in stale_ids:
        if _release_one(appointment_id):
            released += 1

    if released:
        logger.info("Released %s stale pending appointment(s).", released)
    return released


@transaction.atomic
def _release_one(appointment_id: int) -> bool:
    try:
        appointment = Appointment.objects.select_for_update().get(pk=appointment_id)
    except Appointment.DoesNotExist:
        return False

    if appointment.status != Appointment.Status.PENDING_PAYMENT:
        return False

    appointment.status = Appointment.Status.CANCELLED
    appointment.save(update_fields=["status"])

    slot = AvailabilitySlot.objects.select_for_update().get(pk=appointment.slot_id)
    if slot.is_booked:
        slot.is_booked = False
        slot.save(update_fields=["is_booked"])

    return True
