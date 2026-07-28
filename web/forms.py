"""Demo UI forms — thin validation, domain services do the work (Docs/10)."""

from django import forms
from django.utils import timezone

from accounts.models import User


class AvailabilitySlotForm(forms.Form):
    """Practitioner adds an open slot (FR-6)."""

    start_time = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local", "class": "form-control"},
            format="%Y-%m-%dT%H:%M",
        ),
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"],
    )
    end_time = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local", "class": "form-control"},
            format="%Y-%m-%dT%H:%M",
        ),
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"],
    )

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_time")
        end = cleaned.get("end_time")
        if start and end and end <= start:
            self.add_error("end_time", "End time must be after start time.")
        if start and start <= timezone.now():
            self.add_error("start_time", "Start time must be in the future.")
        return cleaned


class CompleteProfileForm(forms.Form):
    role = forms.ChoiceField(choices=User.Role.choices, required=False)

    date_of_birth = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    phone_number = forms.CharField(
        required=False, max_length=32, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    address = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 2, "class": "form-control"})
    )
    emergency_contact_name = forms.CharField(
        required=False, max_length=255, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    emergency_contact_phone = forms.CharField(
        required=False, max_length=32, widget=forms.TextInput(attrs={"class": "form-control"})
    )

    specialization = forms.CharField(
        required=False, max_length=255, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    bio = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"})
    )
    license_number = forms.CharField(
        required=False, max_length=128, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    consultation_fee = forms.DecimalField(
        required=False,
        min_value=0,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
    )

    def __init__(self, *args, user: User, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user.role:
            self.fields["role"].required = False
            self.fields["role"].widget = forms.HiddenInput()
            self.initial["role"] = user.role
        else:
            self.fields["role"].required = True
            # Explicit select — RadioSelect markup was easy to miss / unstyled.
            self.fields["role"].widget = forms.Select(
                attrs={"class": "form-select form-select-lg", "id": "id_role"}
            )
            self.fields["role"].choices = [("", "Select role...")] + list(User.Role.choices)

    def clean(self):
        cleaned = super().clean()
        role = cleaned.get("role") or self.user.role
        if not role:
            self.add_error("role", "Role is required.")
            return cleaned

        if role == User.Role.PATIENT:
            for name in (
                "date_of_birth",
                "phone_number",
                "address",
                "emergency_contact_name",
                "emergency_contact_phone",
            ):
                if not cleaned.get(name):
                    self.add_error(name, "This field is required.")
        elif role == User.Role.PRACTITIONER:
            for name in ("specialization", "bio", "license_number", "consultation_fee"):
                if cleaned.get(name) in (None, ""):
                    self.add_error(name, "This field is required.")
        cleaned["role"] = role
        return cleaned
