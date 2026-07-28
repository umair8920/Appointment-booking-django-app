"""Stripe + webhook + stale-release tests — Docs/06 (Milestone 5)."""

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
from appointments.tasks import release_stale_pending_appointments
from payments.models import Payment
from payments.tasks import process_stripe_webhook_event


def auth_header(user: User) -> dict:
    return {"HTTP_AUTHORIZATION": f"Bearer {RefreshToken.for_user(user).access_token}"}


@override_settings(
    STRIPE_SECRET_KEY="sk_test_dummy",
    STRIPE_PUBLISHABLE_KEY="pk_test_dummy",
    STRIPE_WEBHOOK_SECRET="whsec_dummy",
    PENDING_APPOINTMENT_TIMEOUT_MINUTES=15,
)
class Milestone5PaymentTests(APITestCase):
    def setUp(self):
        self.patient_user = User.objects.create_user(
            email="pay-patient@example.com",
            password="Str0ngPass!word",
            role=User.Role.PATIENT,
            is_profile_complete=True,
        )
        self.practitioner_user = User.objects.create_user(
            email="pay-doc@example.com",
            password="Str0ngPass!word",
            role=User.Role.PRACTITIONER,
            is_profile_complete=True,
        )
        self.practitioner = self.practitioner_user.practitioner_profile
        self.practitioner.consultation_fee = Decimal("50.00")
        self.practitioner.specialization = "GP"
        self.practitioner.save()

        start = timezone.now() + timedelta(days=2)
        self.slot = AvailabilitySlot.objects.create(
            practitioner=self.practitioner,
            start_time=start,
            end_time=start + timedelta(minutes=30),
        )
        self.appointment = Appointment.objects.create(
            patient=self.patient_user.patient_profile,
            practitioner=self.practitioner,
            slot=self.slot,
            status=Appointment.Status.PENDING_PAYMENT,
        )
        self.slot.is_booked = True
        self.slot.save(update_fields=["is_booked"])

    @patch("payments.services.stripe.PaymentIntent.create")
    def test_create_payment_intent(self, mock_create):
        mock_create.return_value = MagicMock(
            id="pi_test_123",
            client_secret="pi_test_123_secret",
        )
        self.client.credentials(**auth_header(self.patient_user))
        response = self.client.post(
            reverse("api_payment_create_intent", kwargs={"appointment_id": self.appointment.id})
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["client_secret"], "pi_test_123_secret")
        self.assertTrue(
            Payment.objects.filter(
                appointment=self.appointment,
                stripe_payment_intent_id="pi_test_123",
                status=Payment.Status.PENDING,
            ).exists()
        )
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args.kwargs
        self.assertEqual(call_kwargs["amount"], 5000)
        self.assertEqual(call_kwargs["currency"], "usd")

    @patch("payments.views.process_stripe_webhook_event.delay")
    @patch("payments.services.stripe.Webhook.construct_event")
    def test_webhook_verifies_and_enqueues_without_db_writes(self, mock_construct, mock_delay):
        mock_construct.return_value = MagicMock(
            to_dict=lambda: {
                "type": "payment_intent.succeeded",
                "data": {"object": {"id": "pi_test_123"}},
            }
        )
        payments_before = Payment.objects.count()
        response = self.client.post(
            reverse("api_payment_stripe_webhook"),
            data=b'{"id":"evt_1"}',
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=1,v1=abc",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Payment.objects.count(), payments_before)
        mock_delay.assert_called_once()

    @patch("payments.services.stripe.Webhook.construct_event", side_effect=ValueError("bad sig"))
    def test_webhook_invalid_signature_returns_400(self, _mock):
        response = self.client.post(
            reverse("api_payment_stripe_webhook"),
            data=b"{}",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="bad",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("integrations.tasks.push_appointment_to_cliniko.delay")
    def test_process_succeeded_confirms_appointment(self, mock_push):
        Payment.objects.create(
            appointment=self.appointment,
            stripe_payment_intent_id="pi_ok",
            amount=Decimal("50.00"),
            status=Payment.Status.PENDING,
        )
        process_stripe_webhook_event(
            {
                "type": "payment_intent.succeeded",
                "data": {"object": {"id": "pi_ok"}},
            }
        )
        self.appointment.refresh_from_db()
        payment = Payment.objects.get(stripe_payment_intent_id="pi_ok")
        self.assertEqual(payment.status, Payment.Status.SUCCEEDED)
        self.assertEqual(self.appointment.status, Appointment.Status.CONFIRMED)
        mock_push.assert_called_once_with(self.appointment.id)

    def test_process_failed_releases_slot(self):
        Payment.objects.create(
            appointment=self.appointment,
            stripe_payment_intent_id="pi_fail",
            amount=Decimal("50.00"),
            status=Payment.Status.PENDING,
        )
        process_stripe_webhook_event(
            {
                "type": "payment_intent.payment_failed",
                "data": {"object": {"id": "pi_fail"}},
            }
        )
        self.appointment.refresh_from_db()
        self.slot.refresh_from_db()
        payment = Payment.objects.get(stripe_payment_intent_id="pi_fail")
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.assertEqual(self.appointment.status, Appointment.Status.CANCELLED)
        self.assertFalse(self.slot.is_booked)

    def test_process_succeeded_idempotent_no_double_push(self):
        Payment.objects.create(
            appointment=self.appointment,
            stripe_payment_intent_id="pi_idem",
            amount=Decimal("50.00"),
            status=Payment.Status.SUCCEEDED,
        )
        self.appointment.status = Appointment.Status.CONFIRMED
        self.appointment.save(update_fields=["status"])

        with patch("integrations.tasks.push_appointment_to_cliniko.delay") as mock_push:
            process_stripe_webhook_event(
                {
                    "type": "payment_intent.succeeded",
                    "data": {"object": {"id": "pi_idem"}},
                }
            )
            mock_push.assert_not_called()

    def test_release_stale_pending_appointments(self):
        self.appointment.created_at = timezone.now() - timedelta(minutes=30)
        self.appointment.save(update_fields=["created_at"])
        # created_at is auto_now_add — may not update via save(update_fields). Use queryset update.
        Appointment.objects.filter(pk=self.appointment.pk).update(
            created_at=timezone.now() - timedelta(minutes=30)
        )

        released = release_stale_pending_appointments()
        self.assertEqual(released, 1)
        self.appointment.refresh_from_db()
        self.slot.refresh_from_db()
        self.assertEqual(self.appointment.status, Appointment.Status.CANCELLED)
        self.assertFalse(self.slot.is_booked)

    def test_charge_refunded_marks_payment(self):
        Payment.objects.create(
            appointment=self.appointment,
            stripe_payment_intent_id="pi_ref",
            amount=Decimal("50.00"),
            status=Payment.Status.SUCCEEDED,
        )
        process_stripe_webhook_event(
            {
                "type": "charge.refunded",
                "data": {"object": {"id": "ch_1", "payment_intent": "pi_ref"}},
            }
        )
        payment = Payment.objects.get(stripe_payment_intent_id="pi_ref")
        self.assertEqual(payment.status, Payment.Status.REFUNDED)
