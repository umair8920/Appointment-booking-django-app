"""Celery tasks — process_stripe_webhook_event (Docs/06)."""

from __future__ import annotations

import logging

from celery import shared_task
from django.db import transaction

from appointments.models import Appointment, AvailabilitySlot
from payments.models import Payment

logger = logging.getLogger(__name__)


@shared_task(name="payments.tasks.process_stripe_webhook_event")
def process_stripe_webhook_event(event_data: dict) -> None:
    """
    Apply Stripe webhook side effects asynchronously (Docs/06).

    Idempotent for redelivered events with the same target status.
    """
    event_type = event_data.get("type")
    data_object = (event_data.get("data") or {}).get("object") or {}

    if event_type == "payment_intent.succeeded":
        _handle_payment_intent_succeeded(data_object)
    elif event_type == "payment_intent.payment_failed":
        _handle_payment_intent_failed(data_object)
    elif event_type == "charge.refunded":
        _handle_charge_refunded(data_object)
    else:
        logger.info("Ignoring unhandled Stripe event type: %s", event_type)


@transaction.atomic
def _handle_payment_intent_succeeded(payment_intent: dict) -> None:
    pi_id = payment_intent.get("id")
    payment = _get_payment(pi_id)
    if payment is None:
        return

    if payment.status == Payment.Status.SUCCEEDED:
        return  # idempotent no-op

    payment.status = Payment.Status.SUCCEEDED
    payment.save(update_fields=["status", "updated_at"])

    appointment = payment.appointment
    if appointment.status != Appointment.Status.CONFIRMED:
        appointment.status = Appointment.Status.CONFIRMED
        appointment.save(update_fields=["status"])

    from integrations.tasks import push_appointment_to_cliniko

    push_appointment_to_cliniko.delay(appointment.id)


@transaction.atomic
def _handle_payment_intent_failed(payment_intent: dict) -> None:
    pi_id = payment_intent.get("id")
    payment = _get_payment(pi_id)
    if payment is None:
        return

    if payment.status == Payment.Status.FAILED:
        return

    payment.status = Payment.Status.FAILED
    payment.save(update_fields=["status", "updated_at"])

    appointment = payment.appointment
    if appointment.status != Appointment.Status.CANCELLED:
        appointment.status = Appointment.Status.CANCELLED
        appointment.save(update_fields=["status"])

    slot = AvailabilitySlot.objects.select_for_update().get(pk=appointment.slot_id)
    if slot.is_booked:
        slot.is_booked = False
        slot.save(update_fields=["is_booked"])


@transaction.atomic
def _handle_charge_refunded(charge: dict) -> None:
    pi_id = charge.get("payment_intent")
    if not pi_id:
        logger.warning("charge.refunded without payment_intent: %s", charge.get("id"))
        return

    payment = _get_payment(pi_id)
    if payment is None:
        return

    if payment.status == Payment.Status.REFUNDED:
        return

    payment.status = Payment.Status.REFUNDED
    payment.save(update_fields=["status", "updated_at"])


def _get_payment(stripe_payment_intent_id: str | None) -> Payment | None:
    if not stripe_payment_intent_id:
        return None
    try:
        return Payment.objects.select_related("appointment", "appointment__slot").get(
            stripe_payment_intent_id=stripe_payment_intent_id
        )
    except Payment.DoesNotExist:
        logger.warning("No Payment for PaymentIntent %s", stripe_payment_intent_id)
        return None
