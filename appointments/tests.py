"""Core booking / profile API tests — Docs/02, 04 (Milestone 4)."""

from datetime import timedelta
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from appointments.models import Appointment, AvailabilitySlot
from patients.models import PatientProfile
from practitioners.models import PractitionerProfile


def auth_header(user: User) -> dict:
    return {"HTTP_AUTHORIZATION": f"Bearer {RefreshToken.for_user(user).access_token}"}


class Milestone4APITests(APITestCase):
    def setUp(self):
        self.patient_user = User.objects.create_user(
            email="patient4@example.com",
            password="Str0ngPass!word",
            role=User.Role.PATIENT,
            is_profile_complete=True,
        )
        self.patient = self.patient_user.patient_profile
        self.patient.phone_number = "111"
        self.patient.address = "A"
        self.patient.emergency_contact_name = "E"
        self.patient.emergency_contact_phone = "222"
        self.patient.save()

        self.practitioner_user = User.objects.create_user(
            email="doc4@example.com",
            password="Str0ngPass!word",
            role=User.Role.PRACTITIONER,
            is_profile_complete=True,
        )
        self.practitioner = self.practitioner_user.practitioner_profile
        self.practitioner.specialization = "Physio"
        self.practitioner.bio = "Bio"
        self.practitioner.license_number = "L-1"
        self.practitioner.consultation_fee = Decimal("50.00")
        self.practitioner.save()

        start = timezone.now() + timedelta(days=1)
        self.slot = AvailabilitySlot.objects.create(
            practitioner=self.practitioner,
            start_time=start,
            end_time=start + timedelta(minutes=30),
            is_booked=False,
            source=AvailabilitySlot.Source.MANUAL,
        )

    def test_list_practitioners(self):
        self.client.credentials(**auth_header(self.patient_user))
        response = self.client.get(reverse("api_practitioner_list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        row = response.data["results"][0]
        self.assertEqual(row["specialization"], "Physio")
        self.assertNotIn("cliniko_practitioner_id", row)

    def test_practitioner_availability_shape(self):
        self.client.credentials(**auth_header(self.patient_user))
        response = self.client.get(
            reverse("api_practitioner_availability", kwargs={"id": self.practitioner.id})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        slot = response.data["results"][0]
        self.assertEqual(set(slot.keys()), {"id", "start_time", "end_time", "is_booked"})
        self.assertFalse(slot["is_booked"])

    def test_patient_me_get_patch(self):
        self.client.credentials(**auth_header(self.patient_user))
        response = self.client.get(reverse("api_patient_me"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.patch(
            reverse("api_patient_me"),
            {"phone_number": "999"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["phone_number"], "999")

    def test_practitioner_me_patch(self):
        self.client.credentials(**auth_header(self.practitioner_user))
        response = self.client.patch(
            reverse("api_practitioner_me"),
            {"consultation_fee": "80.00"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(response.data["consultation_fee"]), Decimal("80.00"))

    def test_book_appointment_marks_slot(self):
        self.client.credentials(**auth_header(self.patient_user))
        response = self.client.post(
            reverse("api_appointment_list_create"),
            {"slot_id": self.slot.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["status"], Appointment.Status.PENDING_PAYMENT)
        self.slot.refresh_from_db()
        self.assertTrue(self.slot.is_booked)

    def test_double_book_rejected(self):
        self.client.credentials(**auth_header(self.patient_user))
        first = self.client.post(
            reverse("api_appointment_list_create"),
            {"slot_id": self.slot.id},
            format="json",
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)

        other = User.objects.create_user(
            email="patient4b@example.com",
            password="Str0ngPass!word",
            role=User.Role.PATIENT,
            is_profile_complete=True,
        )
        self.client.credentials(**auth_header(other))
        second = self.client.post(
            reverse("api_appointment_list_create"),
            {"slot_id": self.slot.id},
            format="json",
        )
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cancel_pending_releases_slot(self):
        self.client.credentials(**auth_header(self.patient_user))
        book = self.client.post(
            reverse("api_appointment_list_create"),
            {"slot_id": self.slot.id},
            format="json",
        )
        appt_id = book.data["id"]
        cancel = self.client.post(reverse("api_appointment_cancel", kwargs={"id": appt_id}))
        self.assertEqual(cancel.status_code, status.HTTP_200_OK)
        self.assertEqual(cancel.data["status"], Appointment.Status.CANCELLED)
        self.slot.refresh_from_db()
        self.assertFalse(self.slot.is_booked)

    def test_list_appointments_role_scoped(self):
        self.client.credentials(**auth_header(self.patient_user))
        self.client.post(
            reverse("api_appointment_list_create"),
            {"slot_id": self.slot.id},
            format="json",
        )
        patient_list = self.client.get(reverse("api_appointment_list_create"))
        self.assertEqual(patient_list.data["count"], 1)

        self.client.credentials(**auth_header(self.practitioner_user))
        prac_list = self.client.get(reverse("api_appointment_list_create"))
        self.assertEqual(prac_list.data["count"], 1)

    def test_incomplete_profile_blocked(self):
        incomplete = User.objects.create_user(
            email="incomplete4@example.com",
            password="Str0ngPass!word",
            role=User.Role.PATIENT,
            is_profile_complete=False,
        )
        self.client.credentials(**auth_header(incomplete))
        response = self.client.get(reverse("api_practitioner_list"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["detail"], "Profile completion required.")
