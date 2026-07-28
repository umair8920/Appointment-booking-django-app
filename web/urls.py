"""Demo UI URL routes — Docs/10."""

from django.urls import path

from web import views

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("complete-profile/", views.CompleteProfileView.as_view(), name="complete_profile"),
    path("practitioners/", views.PractitionerListView.as_view(), name="practitioner_list"),
    path(
        "practitioners/<int:pk>/",
        views.PractitionerDetailView.as_view(),
        name="practitioner_detail",
    ),
    path(
        "appointments/book/<int:slot_id>/",
        views.BookingCheckoutView.as_view(),
        name="booking_checkout",
    ),
    path("my-appointments/", views.MyAppointmentsView.as_view(), name="my_appointments"),
    path("my-schedule/", views.MyScheduleView.as_view(), name="my_schedule"),
    path("staff/", views.StaffDashboardView.as_view(), name="staff_dashboard"),
]
