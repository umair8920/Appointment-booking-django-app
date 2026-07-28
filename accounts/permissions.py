"""DRF permissions for the mandatory profile-completion gate (Docs/05)."""

from rest_framework.permissions import BasePermission


class IsProfileComplete(BasePermission):
    """
    Block API access until the role profile form is submitted.

    Applied as a default DRF permission. Views that must remain reachable
    before completion (auth + complete-profile) should override
    permission_classes accordingly.
    """

    message = "Profile completion required."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return bool(user.is_profile_complete)
