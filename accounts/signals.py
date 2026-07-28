"""Auth signal: empty role profile on user create/role assignment (Docs/05)."""

from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.models import User


@receiver(post_save, sender=User)
def ensure_empty_role_profile(sender, instance: User, **kwargs) -> None:
    """
    Create the empty PatientProfile / PractitionerProfile row when role is set.

    Scoped only to this — not a general signals-everywhere pattern (Docs/01, 05).
    """
    if instance.role == User.Role.PATIENT:
        from patients.models import PatientProfile

        PatientProfile.objects.get_or_create(user=instance)
    elif instance.role == User.Role.PRACTITIONER:
        from practitioners.models import PractitionerProfile

        PractitionerProfile.objects.get_or_create(user=instance)
