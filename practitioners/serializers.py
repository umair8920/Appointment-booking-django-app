"""Practitioner serializers — Docs/03, 04 (no PMS-specific response keys)."""

from rest_framework import serializers

from practitioners.models import PractitionerProfile


class PractitionerSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = PractitionerProfile
        fields = (
            "id",
            "email",
            "specialization",
            "bio",
            "license_number",
            "consultation_fee",
        )
        read_only_fields = ("id", "email")


class PractitionerUpdateSerializer(serializers.ModelSerializer):
    """PATCH /api/practitioners/me/ — own profile fields only."""

    class Meta:
        model = PractitionerProfile
        fields = ("specialization", "bio", "license_number", "consultation_fee")
