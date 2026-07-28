"""Appointment API views — thin, delegate to services (Docs/01, 04)."""

from rest_framework import generics, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from appointments.models import Appointment
from appointments.serializers import AppointmentSerializer, BookAppointmentSerializer
from appointments.services import cancel_appointment, create_appointment
from patients.models import PatientProfile


class AppointmentListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/appointments/"""

    serializer_class = AppointmentSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Appointment.objects.select_related("slot", "patient", "practitioner")
        if user.role == User.Role.PATIENT:
            return qs.filter(patient__user=user)
        if user.role == User.Role.PRACTITIONER:
            return qs.filter(practitioner__user=user)
        return qs.none()

    def create(self, request, *args, **kwargs):
        if request.user.role != User.Role.PATIENT:
            raise PermissionDenied(detail="Only patients can book appointments.")
        try:
            patient = request.user.patient_profile
        except PatientProfile.DoesNotExist as exc:
            raise PermissionDenied(detail="Patient profile not found.") from exc

        serializer = BookAppointmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        appointment = create_appointment(
            patient=patient,
            slot_id=serializer.validated_data["slot_id"],
        )
        return Response(
            AppointmentSerializer(appointment).data,
            status=status.HTTP_201_CREATED,
        )


class AppointmentDetailView(generics.RetrieveAPIView):
    """GET /api/appointments/{id}/"""

    serializer_class = AppointmentSerializer
    lookup_url_kwarg = "id"

    def get_queryset(self):
        user = self.request.user
        qs = Appointment.objects.select_related("slot", "patient", "practitioner")
        if user.role == User.Role.PATIENT:
            return qs.filter(patient__user=user)
        if user.role == User.Role.PRACTITIONER:
            return qs.filter(practitioner__user=user)
        return qs.none()


class AppointmentCancelView(APIView):
    """POST /api/appointments/{id}/cancel/"""

    def post(self, request, id: int, *args, **kwargs):
        try:
            appointment = Appointment.objects.select_related("slot", "patient", "practitioner").get(
                pk=id
            )
        except Appointment.DoesNotExist as exc:
            raise NotFound(detail="Appointment not found.") from exc

        appointment = cancel_appointment(appointment=appointment, acting_user=request.user)
        return Response(AppointmentSerializer(appointment).data, status=status.HTTP_200_OK)
