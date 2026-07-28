"""allauth adapters — role capture for email + Google signup (Docs/05)."""

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.urls import reverse

from accounts.models import User


class AccountAdapter(DefaultAccountAdapter):
    """Session UI: send incomplete profiles to onboarding after login (Docs/10)."""

    def get_login_redirect_url(self, request):
        user = request.user
        if user.is_authenticated and not user.is_profile_complete:
            return reverse("complete_profile")
        return super().get_login_redirect_url(request)


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    On first Google signup, accept optional `role` from the request body
    (API) so OAuth users converge on the same onboarding gate as email signup.
    """

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form=form)
        if user.role:
            return user

        role = None
        if hasattr(request, "data"):
            role = request.data.get("role")
        if role is None and hasattr(request, "POST"):
            role = request.POST.get("role")

        if role in {User.Role.PATIENT, User.Role.PRACTITIONER}:
            user.role = role
            user.save(update_fields=["role"])
        return user
