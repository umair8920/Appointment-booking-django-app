"""Auth / onboarding serializers (Docs/03, 04, 05)."""

from dj_rest_auth.registration.serializers import RegisterSerializer
from rest_framework import serializers

from accounts.models import User
from accounts.services import complete_user_profile


class UserSerializer(serializers.ModelSerializer):
    """GET /api/auth/me/ — current user + role + is_profile_complete."""

    class Meta:
        model = User
        fields = ("id", "email", "role", "is_profile_complete", "first_name", "last_name")
        read_only_fields = fields


class SignupSerializer(RegisterSerializer):
    """POST /api/auth/signup/ — email/password + required role."""

    username = None
    role = serializers.ChoiceField(choices=User.Role.choices)

    def get_cleaned_data(self):
        data = super().get_cleaned_data()
        data["role"] = self.validated_data.get("role")
        return data

    def custom_signup(self, request, user):
        user.role = self.validated_data["role"]
        user.save(update_fields=["role"])


class CompleteProfileSerializer(serializers.Serializer):
    """
    POST /api/auth/complete-profile/ — role-specific fields from Docs/03.

    `role` is accepted only when the user still has a blank role (OAuth path).
    """

    role = serializers.ChoiceField(choices=User.Role.choices, required=False)

    # Patient fields
    date_of_birth = serializers.DateField(required=False)
    phone_number = serializers.CharField(required=False, allow_blank=False, max_length=32)
    address = serializers.CharField(required=False, allow_blank=False)
    emergency_contact_name = serializers.CharField(
        required=False, allow_blank=False, max_length=255
    )
    emergency_contact_phone = serializers.CharField(
        required=False, allow_blank=False, max_length=32
    )

    # Practitioner fields
    specialization = serializers.CharField(required=False, allow_blank=False, max_length=255)
    bio = serializers.CharField(required=False, allow_blank=False)
    license_number = serializers.CharField(required=False, allow_blank=False, max_length=128)
    consultation_fee = serializers.DecimalField(
        required=False, max_digits=10, decimal_places=2, min_value=0
    )

    def validate(self, attrs):
        user: User = self.context["request"].user
        role = attrs.get("role") or user.role
        if not role:
            raise serializers.ValidationError(
                {"role": "Role is required to complete your profile."}
            )
        if user.role and attrs.get("role") and attrs["role"] != user.role:
            raise serializers.ValidationError({"role": "Role cannot be changed once set."})

        if role == User.Role.PATIENT:
            required = (
                "date_of_birth",
                "phone_number",
                "address",
                "emergency_contact_name",
                "emergency_contact_phone",
            )
        else:
            required = ("specialization", "bio", "license_number", "consultation_fee")

        missing = [field for field in required if attrs.get(field) in (None, "")]
        if missing:
            raise serializers.ValidationError(
                {field: "This field is required." for field in missing}
            )
        attrs["role"] = role
        return attrs

    def save(self, **kwargs):
        user = self.context["request"].user
        try:
            return complete_user_profile(user, self.validated_data)
        except ValueError as exc:
            raise serializers.ValidationError({"detail": str(exc)}) from exc
