"""Profile-completion business logic (Docs/05)."""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction

from accounts.models import User
from patients.models import PatientProfile
from practitioners.models import PractitionerProfile


@transaction.atomic
def complete_user_profile(user: User, validated_data: dict) -> User:
    """
    Fill the role profile, set is_profile_complete=True.

    Role may be supplied only when still blank (OAuth first-login path).
    Once set, role is immutable (Docs/03).
    """
    role = validated_data.get("role") or user.role
    if not role:
        raise ValueError("Role is required before completing a profile.")

    if user.role and role != user.role:
        raise ValueError("Role cannot be changed once set.")

    if not user.role:
        user.role = role
        user.save(update_fields=["role"])

    if user.role == User.Role.PATIENT:
        profile, _ = PatientProfile.objects.get_or_create(user=user)
        profile.date_of_birth = validated_data["date_of_birth"]
        profile.phone_number = validated_data["phone_number"]
        profile.address = validated_data["address"]
        profile.emergency_contact_name = validated_data["emergency_contact_name"]
        profile.emergency_contact_phone = validated_data["emergency_contact_phone"]
        profile.save()
    elif user.role == User.Role.PRACTITIONER:
        profile, _ = PractitionerProfile.objects.get_or_create(user=user)
        profile.specialization = validated_data["specialization"]
        profile.bio = validated_data["bio"]
        profile.license_number = validated_data["license_number"]
        fee = validated_data["consultation_fee"]
        profile.consultation_fee = fee if isinstance(fee, Decimal) else Decimal(str(fee))
        profile.save()
    else:
        raise ValueError("Invalid role.")

    user.is_profile_complete = True
    user.save(update_fields=["is_profile_complete"])
    return user
