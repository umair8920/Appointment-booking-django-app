"""Practitioner routes under /api/practitioners/ (Docs/04)."""

from django.urls import path

from practitioners.views import (
    PractitionerAvailabilityView,
    PractitionerDetailView,
    PractitionerListView,
    PractitionerMeView,
)

urlpatterns = [
    path("", PractitionerListView.as_view(), name="api_practitioner_list"),
    path("me/", PractitionerMeView.as_view(), name="api_practitioner_me"),
    path("<int:id>/", PractitionerDetailView.as_view(), name="api_practitioner_detail"),
    path(
        "<int:id>/availability/",
        PractitionerAvailabilityView.as_view(),
        name="api_practitioner_availability",
    ),
]
