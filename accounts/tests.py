"""Auth & onboarding flow tests — Docs/04, 05."""

from datetime import date
from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from patients.models import PatientProfile
from practitioners.models import PractitionerProfile


class AuthOnboardingAPITests(APITestCase):
    def test_signup_creates_empty_patient_profile(self):
        response = self.client.post(
            reverse("api_auth_signup"),
            {
                "email": "patient@example.com",
                "password1": "Str0ngPass!word",
                "password2": "Str0ngPass!word",
                "role": "patient",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        user = User.objects.get(email="patient@example.com")
        self.assertEqual(user.role, User.Role.PATIENT)
        self.assertFalse(user.is_profile_complete)
        self.assertTrue(PatientProfile.objects.filter(user=user).exists())
        self.assertFalse(PractitionerProfile.objects.filter(user=user).exists())

    def test_signup_creates_empty_practitioner_profile(self):
        response = self.client.post(
            reverse("api_auth_signup"),
            {
                "email": "doc@example.com",
                "password1": "Str0ngPass!word",
                "password2": "Str0ngPass!word",
                "role": "practitioner",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        user = User.objects.get(email="doc@example.com")
        self.assertTrue(PractitionerProfile.objects.filter(user=user).exists())

    def test_signup_requires_role(self):
        response = self.client.post(
            reverse("api_auth_signup"),
            {
                "email": "norole@example.com",
                "password1": "Str0ngPass!word",
                "password2": "Str0ngPass!word",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_me_reachable_before_profile_complete(self):
        user = User.objects.create_user(
            email="early@example.com",
            password="Str0ngPass!word",
            role=User.Role.PATIENT,
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}"
        )
        response = self.client.get(reverse("api_auth_me"))
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["email"], "early@example.com")
        self.assertFalse(response.data["is_profile_complete"])
        self.assertEqual(response.data["role"], "patient")

    def test_default_permission_blocks_incomplete_profile_on_other_apis(self):
        """IsProfileComplete is the default — incomplete users get 403 elsewhere."""
        from rest_framework.decorators import api_view, permission_classes
        from rest_framework.permissions import IsAuthenticated
        from rest_framework.response import Response
        from rest_framework.test import APIRequestFactory, force_authenticate

        from accounts.permissions import IsProfileComplete

        @api_view(["GET"])
        @permission_classes([IsAuthenticated, IsProfileComplete])
        def gated(_request):
            return Response({"ok": True})

        user = User.objects.create_user(
            email="gated@example.com",
            password="Str0ngPass!word",
            role=User.Role.PATIENT,
        )
        factory = APIRequestFactory()
        request = factory.get("/gated/")
        force_authenticate(request, user=user)
        response = gated(request)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["detail"], "Profile completion required.")

    def test_complete_patient_profile(self):
        user = User.objects.create_user(
            email="complete-p@example.com",
            password="Str0ngPass!word",
            role=User.Role.PATIENT,
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}"
        )
        response = self.client.post(
            reverse("api_auth_complete_profile"),
            {
                "date_of_birth": "1990-05-01",
                "phone_number": "+15551212",
                "address": "1 Test St",
                "emergency_contact_name": "Jane Doe",
                "emergency_contact_phone": "+15559876",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        user.refresh_from_db()
        self.assertTrue(user.is_profile_complete)
        profile = user.patient_profile
        self.assertEqual(profile.date_of_birth, date(1990, 5, 1))
        self.assertEqual(profile.phone_number, "+15551212")

    def test_complete_practitioner_profile(self):
        user = User.objects.create_user(
            email="complete-d@example.com",
            password="Str0ngPass!word",
            role=User.Role.PRACTITIONER,
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}"
        )
        response = self.client.post(
            reverse("api_auth_complete_profile"),
            {
                "specialization": "Physiotherapy",
                "bio": "Experienced physio",
                "license_number": "LIC-123",
                "consultation_fee": "75.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        user.refresh_from_db()
        self.assertTrue(user.is_profile_complete)
        self.assertEqual(user.practitioner_profile.consultation_fee, Decimal("75.00"))

    def test_login_returns_jwt(self):
        User.objects.create_user(
            email="login@example.com",
            password="Str0ngPass!word",
            role=User.Role.PATIENT,
        )
        response = self.client.post(
            reverse("api_auth_login"),
            {"email": "login@example.com", "password": "Str0ngPass!word"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_role_immutable_on_complete_profile(self):
        user = User.objects.create_user(
            email="immutable@example.com",
            password="Str0ngPass!word",
            role=User.Role.PATIENT,
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}"
        )
        response = self.client.post(
            reverse("api_auth_complete_profile"),
            {
                "role": "practitioner",
                "date_of_birth": "1990-05-01",
                "phone_number": "+15551212",
                "address": "1 Test St",
                "emergency_contact_name": "Jane",
                "emergency_contact_phone": "+15559876",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
