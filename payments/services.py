"""Stripe PaymentIntent creation and refunds (Docs/06).

create-intent + webhook land in Milestone 5.
refund_payment is wired now so appointment cancel (FR-14) has a service seam.
"""

from __future__ import annotations

import logging

from appointments.models import Appointment
from payments.models import Payment

logger = logging.getLogger(__name__)


def refund_payment(appointment: Appointment) -> None:
    """
    Refund a succeeded payment for a cancelled appointment (FR-14).

    Milestone 5 replaces the body with a real Stripe Refund call. Until then,
    if a succeeded Payment row exists we mark it refunded so cancel stays
    consistent locally.
    """
    try:
        payment = appointment.payment
    except Payment.DoesNotExist:
        return

    if payment.status != Payment.Status.SUCCEEDED:
        return

    # TODO(Milestone 5): stripe.Refund.create(payment_intent=...)
    payment.status = Payment.Status.REFUNDED
    payment.save(update_fields=["status", "updated_at"])
    logger.info(
        "Marked payment %s refunded for appointment %s (Stripe refund in M5).",
        payment.pk,
        appointment.pk,
    )
