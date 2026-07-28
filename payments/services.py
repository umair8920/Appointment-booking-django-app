"""Stripe PaymentIntent creation and refunds (Docs/06).

Aligned with Stripe docs: server-side PaymentIntent + Elements client,
webhook is the source of truth for fulfillment (not client-side status).
"""

from __future__ import annotations

import logging
from decimal import Decimal

import stripe
from django.conf import settings
from rest_framework.exceptions import PermissionDenied, ValidationError

from appointments.models import Appointment
from payments.models import Payment

logger = logging.getLogger(__name__)


def _configure_stripe() -> None:
    secret = settings.STRIPE_SECRET_KEY
    if not secret or secret.endswith("replace_me"):
        raise ValidationError({"detail": "Stripe is not configured."})
    stripe.api_key = secret


def create_payment_intent(*, appointment: Appointment, acting_user) -> dict:
    """
    Create (or reuse) a Stripe PaymentIntent for a pending appointment.

    Returns client_secret for Stripe Elements. Never handles raw card data.
    """
    if appointment.patient.user_id != acting_user.id:
        raise PermissionDenied(detail="You can only pay for your own appointments.")

    if appointment.status != Appointment.Status.PENDING_PAYMENT:
        raise ValidationError(
            {"detail": "Payment can only be started for appointments pending payment."}
        )

    fee = appointment.practitioner.consultation_fee
    if fee is None or fee <= 0:
        raise ValidationError({"detail": "Practitioner consultation fee is not set."})

    amount = Decimal(fee).quantize(Decimal("0.01"))
    currency = "usd"
    amount_cents = int(amount * 100)

    existing = Payment.objects.filter(appointment=appointment).first()
    if existing:
        if existing.status != Payment.Status.PENDING:
            raise ValidationError({"detail": f"Payment is already {existing.status}."})
        _configure_stripe()
        intent = stripe.PaymentIntent.retrieve(existing.stripe_payment_intent_id)
        return {
            "client_secret": intent.client_secret,
            "payment_intent_id": intent.id,
            "publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
            "amount": str(existing.amount),
            "currency": existing.currency,
        }

    _configure_stripe()
    # Idempotency key prevents duplicate PaymentIntents on client retries.
    intent = stripe.PaymentIntent.create(
        amount=amount_cents,
        currency=currency,
        metadata={
            "appointment_id": str(appointment.pk),
            "patient_id": str(appointment.patient_id),
            "practitioner_id": str(appointment.practitioner_id),
        },
        automatic_payment_methods={"enabled": True},
        idempotency_key=f"appointment-{appointment.pk}-payment-intent",
    )

    Payment.objects.create(
        appointment=appointment,
        stripe_payment_intent_id=intent.id,
        amount=amount,
        currency=currency,
        status=Payment.Status.PENDING,
    )

    return {
        "client_secret": intent.client_secret,
        "payment_intent_id": intent.id,
        "publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
        "amount": str(amount),
        "currency": currency,
    }


def refund_payment(appointment: Appointment) -> None:
    """Refund a succeeded payment via Stripe (FR-14 / Docs/06)."""
    try:
        payment = appointment.payment
    except Payment.DoesNotExist:
        return

    if payment.status != Payment.Status.SUCCEEDED:
        return

    _configure_stripe()
    try:
        stripe.Refund.create(
            payment_intent=payment.stripe_payment_intent_id,
            idempotency_key=f"appointment-{appointment.pk}-refund",
        )
    except stripe.error.InvalidRequestError as exc:
        # Already refunded on Stripe side — still mark local row.
        if "already been refunded" not in str(exc).lower():
            raise

    payment.status = Payment.Status.REFUNDED
    payment.save(update_fields=["status", "updated_at"])
    logger.info(
        "Refunded payment %s for appointment %s.",
        payment.pk,
        appointment.pk,
    )


def verify_stripe_webhook(payload: bytes, sig_header: str | None) -> dict:
    """
    Verify Stripe-Signature. Returns the event as a plain dict.
    Raises ValueError / stripe.error.SignatureVerificationError on failure.
    """
    secret = settings.STRIPE_WEBHOOK_SECRET
    if not secret or secret.endswith("replace_me"):
        raise ValueError("STRIPE_WEBHOOK_SECRET is not configured.")
    if not sig_header:
        raise ValueError("Missing Stripe-Signature header.")

    stripe.api_key = settings.STRIPE_SECRET_KEY
    event = stripe.Webhook.construct_event(payload, sig_header, secret)
    if hasattr(event, "to_dict"):
        return event.to_dict()
    return dict(event)
