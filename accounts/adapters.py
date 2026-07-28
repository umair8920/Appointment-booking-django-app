"""allauth adapters — role capture for email + Google signup (Docs/05)."""

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

from accounts.models import User


class AccountAdapter(DefaultAccountAdapter):
    """Pass-through; role is set by the API signup serializer / forms."""

    pass


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
