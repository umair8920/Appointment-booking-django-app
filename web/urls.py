"""Demo UI URL routes — mounted at '/' (Docs/10). Full page logic in Milestone 8."""

from django.urls import path
from django.views.generic import TemplateView

urlpatterns = [
    path("", TemplateView.as_view(template_name="web/home.html"), name="home"),
    path(
        "complete-profile/",
        TemplateView.as_view(template_name="web/complete_profile.html"),
        name="complete_profile",
    ),
    path(
        "practitioners/",
        TemplateView.as_view(template_name="web/practitioner_list.html"),
        name="practitioner_list",
    ),
    path(
        "practitioners/<int:pk>/",
        TemplateView.as_view(template_name="web/practitioner_detail.html"),
        name="practitioner_detail",
    ),
    path(
        "appointments/book/<int:slot_id>/",
        TemplateView.as_view(template_name="web/booking_checkout.html"),
        name="booking_checkout",
    ),
    path(
        "my-appointments/",
        TemplateView.as_view(template_name="web/my_appointments.html"),
        name="my_appointments",
    ),
    path(
        "my-schedule/",
        TemplateView.as_view(template_name="web/my_schedule.html"),
        name="my_schedule",
    ),
]
