"""Practitioner API views — Docs/04."""

from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from appointments.models import AvailabilitySlot
from appointments.serializers import AvailabilitySlotSerializer
from practitioners.models import PractitionerProfile
from practitioners.serializers import PractitionerSerializer, PractitionerUpdateSerializer


class PractitionerListView(generics.ListAPIView):
    """GET /api/practitioners/"""

    serializer_class = PractitionerSerializer

    def get_queryset(self):
        return (
            PractitionerProfile.objects.filter(
                user__role=User.Role.PRACTITIONER,
                user__is_profile_complete=True,
            )
            .select_related("user")
            .order_by("id")
        )


class PractitionerDetailView(generics.RetrieveAPIView):
    """GET /api/practitioners/{id}/"""

    serializer_class = PractitionerSerializer
    lookup_url_kwarg = "id"

    def get_queryset(self):
        return PractitionerProfile.objects.filter(
            user__role=User.Role.PRACTITIONER,
            user__is_profile_complete=True,
        ).select_related("user")


class PractitionerAvailabilityView(generics.ListAPIView):
    """GET /api/practitioners/{id}/availability/ — open slots only."""

    serializer_class = AvailabilitySlotSerializer

    def get_queryset(self):
        practitioner_id = self.kwargs["id"]
        if not PractitionerProfile.objects.filter(
            pk=practitioner_id,
            user__is_profile_complete=True,
        ).exists():
            return AvailabilitySlot.objects.none()
        return AvailabilitySlot.objects.filter(
            practitioner_id=practitioner_id,
            is_booked=False,
        ).order_by("start_time")

    def list(self, request, *args, **kwargs):
        if not PractitionerProfile.objects.filter(
            pk=self.kwargs["id"],
            user__is_profile_complete=True,
        ).exists():
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return super().list(request, *args, **kwargs)


class PractitionerMeView(APIView):
    """PATCH /api/practitioners/me/"""

    def get_profile(self, request) -> PractitionerProfile:
        if request.user.role != User.Role.PRACTITIONER:
            raise PermissionDenied(detail="Practitioner role required.")
        try:
            return request.user.practitioner_profile
        except PractitionerProfile.DoesNotExist as exc:
            raise PermissionDenied(detail="Practitioner profile not found.") from exc

    def patch(self, request, *args, **kwargs):
        profile = self.get_profile(request)
        serializer = PractitionerUpdateSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(PractitionerSerializer(profile).data)
