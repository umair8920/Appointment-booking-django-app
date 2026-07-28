"""Business logic for booking and cancellation (Docs/01, 02, 04)."""

from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.models import User
from appointments.models import Appointment, AvailabilitySlot
from patients.models import PatientProfile


class AppointmentServiceError(Exception):
    """Domain error raised by appointment services."""


@transaction.atomic
def create_appointment(*, patient: PatientProfile, slot_id: int) -> Appointment:
    """
    Book a slot → Appointment(pending_payment), mark slot booked (FR-11, NFR-3).

    Uses select_for_update so concurrent bookings cannot double-book the same slot.
    """
    try:
        slot = (
            AvailabilitySlot.objects.select_for_update()
            .select_related("practitioner")
            .get(pk=slot_id)
        )
    except AvailabilitySlot.DoesNotExist as exc:
        raise ValidationError({"slot_id": "Availability slot not found."}) from exc

    if slot.is_booked:
        raise ValidationError({"slot_id": "This slot is no longer available."})

    if slot.start_time <= timezone.now():
        raise ValidationError({"slot_id": "Cannot book a slot in the past."})

    slot.is_booked = True
    slot.save(update_fields=["is_booked"])

    try:
        appointment = Appointment.objects.create(
            patient=patient,
            practitioner=slot.practitioner,
            slot=slot,
            status=Appointment.Status.PENDING_PAYMENT,
        )
    except IntegrityError as exc:
        raise ValidationError({"slot_id": "This slot is no longer available."}) from exc

    return appointment


@transaction.atomic
def cancel_appointment(*, appointment: Appointment, acting_user: User) -> Appointment:
    """
    Cancel an appointment, release the slot, refund via payments service if confirmed (FR-10, FR-14).
    """
    _assert_can_cancel(appointment, acting_user)

    if appointment.status == Appointment.Status.CANCELLED:
        raise ValidationError({"detail": "Appointment is already cancelled."})

    if appointment.status == Appointment.Status.COMPLETED:
        raise ValidationError({"detail": "Completed appointments cannot be cancelled."})

    was_confirmed = appointment.status == Appointment.Status.CONFIRMED

    appointment.status = Appointment.Status.CANCELLED
    appointment.save(update_fields=["status"])

    slot = AvailabilitySlot.objects.select_for_update().get(pk=appointment.slot_id)
    slot.is_booked = False
    slot.save(update_fields=["is_booked"])

    if was_confirmed:
        # Cross-app call via service layer (Docs/01) — Stripe body filled in Milestone 5.
        from payments.services import refund_payment

        refund_payment(appointment)

    return appointment


def _assert_can_cancel(appointment: Appointment, acting_user: User) -> None:
    if acting_user.role == User.Role.PATIENT:
        if (
            not hasattr(acting_user, "patient_profile")
            or appointment.patient_id != acting_user.patient_profile.id
        ):
            raise PermissionDenied(detail="You can only cancel your own appointments.")
        return
    if acting_user.role == User.Role.PRACTITIONER:
        if (
            not hasattr(acting_user, "practitioner_profile")
            or appointment.practitioner_id != acting_user.practitioner_profile.id
        ):
            raise PermissionDenied(detail="You can only cancel appointments on your schedule.")
        return
    raise PermissionDenied(detail="Not allowed to cancel appointments.")
