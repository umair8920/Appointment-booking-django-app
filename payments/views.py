"""Payment API views — create-intent + Stripe webhook (Docs/04, 06)."""

from __future__ import annotations

import logging

import stripe
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from appointments.models import Appointment
from payments.services import create_payment_intent, verify_stripe_webhook
from payments.tasks import process_stripe_webhook_event

logger = logging.getLogger(__name__)


class CreatePaymentIntentView(APIView):
    """POST /api/payments/{appointment_id}/create-intent/"""

    permission_classes = [IsAuthenticated]

    def post(self, request, appointment_id: int, *args, **kwargs):
        try:
            appointment = Appointment.objects.select_related(
                "patient__user",
                "practitioner",
            ).get(pk=appointment_id)
        except Appointment.DoesNotExist as exc:
            raise NotFound(detail="Appointment not found.") from exc

        result = create_payment_intent(appointment=appointment, acting_user=request.user)
        return Response(result, status=status.HTTP_201_CREATED)


class StripeWebhookView(APIView):
    """
    POST /api/payments/webhook/stripe/

    Verify signature → enqueue Celery task → return 200 immediately.
    Does not touch the database (Docs/06).
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")

        try:
            event_data = verify_stripe_webhook(payload, sig_header)
        except (ValueError, stripe.error.SignatureVerificationError) as exc:
            logger.warning("Stripe webhook rejected: %s", exc)
            return Response({"detail": "Invalid signature."}, status=status.HTTP_400_BAD_REQUEST)

        process_stripe_webhook_event.delay(event_data)
        return Response({"received": True}, status=status.HTTP_200_OK)
