"""allauth signup form — capture role at signup (Docs/05, FR-3)."""

from allauth.account.forms import SignupForm as AllauthSignupForm
from django import forms

from accounts.models import User


class SignupForm(AllauthSignupForm):
    role = forms.ChoiceField(
        choices=User.Role.choices,
        widget=forms.RadioSelect,
        label="I am a",
    )

    def save(self, request):
        user = super().save(request)
        user.role = self.cleaned_data["role"]
        user.save(update_fields=["role"])
        return user
