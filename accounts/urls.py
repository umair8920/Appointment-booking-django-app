"""Auth routes under /api/auth/ (Docs/04)."""

from django.urls import path

from accounts.views import (
    CompleteProfileView,
    EmailLoginView,
    EmailLogoutView,
    GoogleLoginView,
    MeView,
    SignupView,
)

urlpatterns = [
    path("signup/", SignupView.as_view(), name="api_auth_signup"),
    path("login/", EmailLoginView.as_view(), name="api_auth_login"),
    path("logout/", EmailLogoutView.as_view(), name="api_auth_logout"),
    path("me/", MeView.as_view(), name="api_auth_me"),
    path("complete-profile/", CompleteProfileView.as_view(), name="api_auth_complete_profile"),
    path("google/", GoogleLoginView.as_view(), name="api_auth_google"),
]
