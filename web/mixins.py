"""
UI gate: redirect incomplete profiles to complete-profile (Docs/10).

Same check as accounts.permissions.IsProfileComplete; redirect instead of 403.
Implemented fully in Milestone 8.
"""

from django.contrib.auth.mixins import AccessMixin
from django.http import HttpResponseForbidden
from django.urls import reverse_lazy


class ProfileCompleteRequiredMixin(AccessMixin):
    """Require login + completed profile for template views."""

    login_url = reverse_lazy("account_login")
    profile_complete_url = reverse_lazy("complete_profile")

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_profile_complete:
            from django.shortcuts import redirect

            return redirect(self.profile_complete_url)
        return super().dispatch(request, *args, **kwargs)


class StaffRequiredMixin(AccessMixin):
    """Staff-only demo admin panel (login required; profile complete not required)."""

    login_url = reverse_lazy("account_login")

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_staff:
            return HttpResponseForbidden("Staff access required.")
        return super().dispatch(request, *args, **kwargs)
