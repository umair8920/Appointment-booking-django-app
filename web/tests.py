"""Minimal web UI smoke tests — Docs/10."""

from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from appointments.models import AvailabilitySlot


class WebUISmokeTests(TestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            email="web-patient@example.com",
            password="Str0ngPass!word",
            role=User.Role.PATIENT,
            is_profile_complete=True,
        )
        self.practitioner = User.objects.create_user(
            email="web-doc@example.com",
            password="Str0ngPass!word",
            role=User.Role.PRACTITIONER,
            is_profile_complete=True,
        )
        profile = self.practitioner.practitioner_profile
        profile.specialization = "Physio"
        profile.consultation_fee = Decimal("55.00")
        profile.bio = "Hello"
        profile.license_number = "L-9"
        profile.save()
        start = timezone.now() + timedelta(days=2)
        self.slot = AvailabilitySlot.objects.create(
            practitioner=profile,
            start_time=start,
            end_time=start + timedelta(minutes=30),
        )

    def test_home_public(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ClinicBook")

    def test_incomplete_profile_redirects(self):
        incomplete = User.objects.create_user(
            email="web-incomplete@example.com",
            password="Str0ngPass!word",
            role=User.Role.PATIENT,
            is_profile_complete=False,
        )
        self.client.force_login(incomplete)
        response = self.client.get(reverse("practitioner_list"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/complete-profile/", response.url)

    def test_practitioner_list_and_detail(self):
        self.client.force_login(self.patient)
        listing = self.client.get(reverse("practitioner_list"))
        self.assertEqual(listing.status_code, 200)
        self.assertContains(listing, "Physio")

        detail = self.client.get(
            reverse("practitioner_detail", kwargs={"pk": self.practitioner.practitioner_profile.id})
        )
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Book")

    def test_booking_checkout_creates_pending_appointment(self):
        self.client.force_login(self.patient)
        response = self.client.get(reverse("booking_checkout", kwargs={"slot_id": self.slot.id}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pay now")
        self.slot.refresh_from_db()
        self.assertTrue(self.slot.is_booked)

    def test_my_appointments_and_schedule(self):
        self.client.force_login(self.patient)
        self.assertEqual(self.client.get(reverse("my_appointments")).status_code, 200)
        self.client.force_login(self.practitioner)
        self.assertEqual(self.client.get(reverse("my_schedule")).status_code, 200)
