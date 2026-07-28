"""
Cross-cutting payment + webhook flow — Docs/01 steps 4–9, Docs/06.

create-intent → webhook verify/enqueue → Celery task confirms appointment
and enqueues Cliniko push.
"""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from appointments.models import Appointment, AvailabilitySlot
from payments.models import Payment
from payments.tasks import process_stripe_webhook_event


def _auth(user: User) -> dict:
    return {"HTTP_AUTHORIZATION": f"Bearer {RefreshToken.for_user(user).access_token}"}


@override_settings(
    STRIPE_SECRET_KEY="sk_test_dummy",
    STRIPE_PUBLISHABLE_KEY="pk_test_dummy",
    STRIPE_WEBHOOK_SECRET="whsec_dummy",
)
class PaymentWebhookFlowTests(APITestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            email="payflow-patient@example.com",
            password="Str0ngPass!word",
            role=User.Role.PATIENT,
            is_profile_complete=True,
        )
        self.practitioner = User.objects.create_user(
            email="payflow-doc@example.com",
            password="Str0ngPass!word",
            role=User.Role.PRACTITIONER,
            is_profile_complete=True,
        )
        profile = self.practitioner.practitioner_profile
        profile.consultation_fee = Decimal("75.00")
        profile.save()

        start = timezone.now() + timedelta(days=4)
        self.slot = AvailabilitySlot.objects.create(
            practitioner=profile,
            start_time=start,
            end_time=start + timedelta(minutes=30),
            is_booked=True,
        )
        self.appointment = Appointment.objects.create(
            patient=self.patient.patient_profile,
            practitioner=profile,
            slot=self.slot,
            status=Appointment.Status.PENDING_PAYMENT,
        )

    @patch("payments.services.stripe.PaymentIntent.create")
    def test_create_intent_then_succeeded_webhook_confirms(self, mock_create):
        mock_create.return_value = MagicMock(
            id="pi_flow_1",
            client_secret="pi_flow_1_secret",
        )
        self.client.credentials(**_auth(self.patient))
        intent = self.client.post(
            reverse(
                "api_payment_create_intent",
                kwargs={"appointment_id": self.appointment.id},
            )
        )
        self.assertEqual(intent.status_code, status.HTTP_201_CREATED, intent.data)
        self.assertEqual(intent.data["client_secret"], "pi_flow_1_secret")
        self.assertTrue(
            Payment.objects.filter(
                appointment=self.appointment,
                stripe_payment_intent_id="pi_flow_1",
                status=Payment.Status.PENDING,
            ).exists()
        )

        with patch("integrations.tasks.push_appointment_to_cliniko.delay") as mock_push:
            process_stripe_webhook_event(
                {
                    "type": "payment_intent.succeeded",
                    "data": {"object": {"id": "pi_flow_1"}},
                }
            )
            mock_push.assert_called_once_with(self.appointment.id)

        self.appointment.refresh_from_db()
        payment = Payment.objects.get(stripe_payment_intent_id="pi_flow_1")
        self.assertEqual(payment.status, Payment.Status.SUCCEEDED)
        self.assertEqual(self.appointment.status, Appointment.Status.CONFIRMED)

    @patch("payments.views.process_stripe_webhook_event.delay")
    @patch("payments.services.stripe.Webhook.construct_event")
    def test_webhook_endpoint_enqueues_without_db_writes(self, mock_construct, mock_delay):
        mock_construct.return_value = MagicMock(
            to_dict=lambda: {
                "type": "payment_intent.succeeded",
                "data": {"object": {"id": "pi_x"}},
            }
        )
        before = Payment.objects.count()
        response = self.client.post(
            reverse("api_payment_stripe_webhook"),
            data=b'{"id":"evt_flow"}',
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=1,v1=abc",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Payment.objects.count(), before)
        mock_delay.assert_called_once()
