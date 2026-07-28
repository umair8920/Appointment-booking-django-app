"""Patient API views — Docs/04."""

from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from patients.models import PatientProfile
from patients.serializers import PatientProfileSerializer, PatientProfileUpdateSerializer


class PatientMeView(APIView):
    """GET/PATCH /api/patients/me/"""

    def get_profile(self, request) -> PatientProfile:
        if request.user.role != User.Role.PATIENT:
            raise PermissionDenied(detail="Patient role required.")
        try:
            return request.user.patient_profile
        except PatientProfile.DoesNotExist as exc:
            raise PermissionDenied(detail="Patient profile not found.") from exc

    def get(self, request, *args, **kwargs):
        profile = self.get_profile(request)
        return Response(PatientProfileSerializer(profile).data)

    def patch(self, request, *args, **kwargs):
        profile = self.get_profile(request)
        serializer = PatientProfileUpdateSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(PatientProfileSerializer(profile).data)
