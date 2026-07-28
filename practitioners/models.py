"""PractitionerProfile — contract from Docs/03_DATA_MODELS.md."""

from django.conf import settings
from django.db import models


class PractitionerProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="practitioner_profile",
    )
    # blank/null allowed so an empty row can exist before complete-profile (Docs/05).
    specialization = models.CharField(max_length=255, blank=True, default="")
    bio = models.TextField(blank=True, default="")
    license_number = models.CharField(max_length=128, blank=True, default="")
    consultation_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Platform base currency (see payments.Payment.currency).",
    )
    cliniko_practitioner_id = models.CharField(
        max_length=128,
        null=True,
        blank=True,
        help_text="External Cliniko mapping — single nullable field (Docs/01, 07).",
    )

    class Meta:
        verbose_name = "practitioner profile"
        verbose_name_plural = "practitioner profiles"

    def __str__(self) -> str:
        return f"PractitionerProfile<{self.user_id}>"
