"""Patient routes under /api/patients/ (Docs/04)."""

from django.urls import path

from patients.views import PatientMeView

urlpatterns = [
    path("me/", PatientMeView.as_view(), name="api_patient_me"),
]
