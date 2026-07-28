from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    # Demo UI (session auth) — Docs/10
    path("", include("web.urls")),
    path("accounts/", include("allauth.urls")),
    # DRF API — Docs/04
    path("api/auth/", include("accounts.urls")),
    path("api/patients/", include("patients.urls")),
    path("api/practitioners/", include("practitioners.urls")),
    path("api/appointments/", include("appointments.urls")),
    path("api/payments/", include("payments.urls")),
]
