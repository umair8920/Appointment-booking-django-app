"""
Cross-cutting booking flow — Docs/01 steps 1–3, NFR-3 / FR-9–11.

Booking creates pending_payment appointment and locks the slot.
"""

from datetime import timedelta
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from appointments.models import Appointment, AvailabilitySlot


def _auth(user: User) -> dict:
    return {"HTTP_AUTHORIZATION": f"Bearer {RefreshToken.for_user(user).access_token}"}


class BookingFlowTests(APITestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            email="flow-patient@example.com",
            password="Str0ngPass!word",
            role=User.Role.PATIENT,
            is_profile_complete=True,
        )
        self.practitioner = User.objects.create_user(
            email="flow-doc@example.com",
            password="Str0ngPass!word",
            role=User.Role.PRACTITIONER,
            is_profile_complete=True,
        )
        profile = self.practitioner.practitioner_profile
        profile.specialization = "GP"
        profile.consultation_fee = Decimal("60.00")
        profile.save()

        start = timezone.now() + timedelta(days=3)
        self.slot = AvailabilitySlot.objects.create(
            practitioner=profile,
            start_time=start,
            end_time=start + timedelta(minutes=30),
            source=AvailabilitySlot.Source.MANUAL,
        )

    def test_patient_lists_practitioners_and_books_slot(self):
        self.client.credentials(**_auth(self.patient))

        practitioners = self.client.get(reverse("api_practitioner_list"))
        self.assertEqual(practitioners.status_code, status.HTTP_200_OK)
        self.assertEqual(practitioners.data["count"], 1)

        availability = self.client.get(
            reverse(
                "api_practitioner_availability",
                kwargs={"id": self.practitioner.practitioner_profile.id},
            )
        )
        self.assertEqual(availability.status_code, status.HTTP_200_OK)
        self.assertEqual(availability.data["count"], 1)
        self.assertEqual(
            set(availability.data["results"][0].keys()),
            {"id", "start_time", "end_time", "is_booked"},
        )

        book = self.client.post(
            reverse("api_appointment_list_create"),
            {"slot_id": self.slot.id},
            format="json",
        )
        self.assertEqual(book.status_code, status.HTTP_201_CREATED, book.data)
        self.assertEqual(book.data["status"], Appointment.Status.PENDING_PAYMENT)

        self.slot.refresh_from_db()
        self.assertTrue(self.slot.is_booked)

        # Double-book rejected (NFR-3)
        other = User.objects.create_user(
            email="flow-patient-2@example.com",
            password="Str0ngPass!word",
            role=User.Role.PATIENT,
            is_profile_complete=True,
        )
        self.client.credentials(**_auth(other))
        again = self.client.post(
            reverse("api_appointment_list_create"),
            {"slot_id": self.slot.id},
            format="json",
        )
        self.assertEqual(again.status_code, status.HTTP_400_BAD_REQUEST)
