"""Auth API views — Docs/04, 05. Bypass IsProfileComplete (auth endpoints)."""

from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from dj_rest_auth.registration.views import RegisterView, SocialLoginView
from dj_rest_auth.views import LoginView, LogoutView, UserDetailsView
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.serializers import CompleteProfileSerializer, UserSerializer


class SignupView(RegisterView):
    """POST /api/auth/signup/"""

    permission_classes = [AllowAny]


class EmailLoginView(LoginView):
    """POST /api/auth/login/"""

    permission_classes = [AllowAny]


class EmailLogoutView(LogoutView):
    """POST /api/auth/logout/"""

    permission_classes = [IsAuthenticated]


class MeView(UserDetailsView):
    """GET /api/auth/me/ — reachable before profile completion (Docs/05)."""

    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer


class CompleteProfileView(APIView):
    """POST /api/auth/complete-profile/ — profile-complete check bypassed."""

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        if request.user.is_profile_complete:
            return Response(
                {"detail": "Profile is already complete."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = CompleteProfileSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)


class GoogleLoginView(SocialLoginView):
    """
    GET/POST /api/auth/google/ — OAuth entry for API clients (Docs/04).

    POST body typically includes access_token (or code) and optional `role`
    for first-time signup (patient | practitioner).
    """

    adapter_class = GoogleOAuth2Adapter
    client_class = OAuth2Client
    permission_classes = [AllowAny]

    @property
    def callback_url(self):
        from django.conf import settings

        return getattr(
            settings,
            "GOOGLE_OAUTH_CALLBACK_URL",
            "http://localhost:8000/accounts/google/login/callback/",
        )
