"""PatientProfile — contract from Docs/03_DATA_MODELS.md."""

from django.conf import settings
from django.db import models


class PatientProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="patient_profile",
    )
    # blank/null allowed so an empty row can exist before complete-profile (Docs/05).
    date_of_birth = models.DateField(null=True, blank=True)
    phone_number = models.CharField(max_length=32, blank=True, default="")
    address = models.TextField(blank=True, default="")
    emergency_contact_name = models.CharField(max_length=255, blank=True, default="")
    emergency_contact_phone = models.CharField(max_length=32, blank=True, default="")

    class Meta:
        verbose_name = "patient profile"
        verbose_name_plural = "patient profiles"

    def __str__(self) -> str:
        return f"PatientProfile<{self.user_id}>"
