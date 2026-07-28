"""Appointment routes under /api/appointments/ (Docs/04)."""

from django.urls import path

from appointments.views import (
    AppointmentCancelView,
    AppointmentDetailView,
    AppointmentListCreateView,
)

urlpatterns = [
    path("", AppointmentListCreateView.as_view(), name="api_appointment_list_create"),
    path("<int:id>/", AppointmentDetailView.as_view(), name="api_appointment_detail"),
    path("<int:id>/cancel/", AppointmentCancelView.as_view(), name="api_appointment_cancel"),
]
