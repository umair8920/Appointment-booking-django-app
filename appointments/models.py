"""AvailabilitySlot + Appointment — contract from Docs/03_DATA_MODELS.md."""

from django.db import models


class AvailabilitySlot(models.Model):
    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        CLINIKO = "cliniko", "Cliniko"

    practitioner = models.ForeignKey(
        "practitioners.PractitionerProfile",
        on_delete=models.CASCADE,
        related_name="availability_slots",
    )
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    is_booked = models.BooleanField(default=False)
    source = models.CharField(
        max_length=32,
        choices=Source.choices,
        default=Source.MANUAL,
    )

    class Meta:
        verbose_name = "availability slot"
        verbose_name_plural = "availability slots"
        constraints = [
            models.UniqueConstraint(
                fields=["practitioner", "start_time"],
                name="uniq_slot_practitioner_start_time",
            ),
        ]
        ordering = ["start_time"]

    def __str__(self) -> str:
        return f"Slot<{self.practitioner_id} {self.start_time.isoformat()}>"


class Appointment(models.Model):
    class Status(models.TextChoices):
        PENDING_PAYMENT = "pending_payment", "Pending payment"
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"

    patient = models.ForeignKey(
        "patients.PatientProfile",
        on_delete=models.CASCADE,
        related_name="appointments",
    )
    practitioner = models.ForeignKey(
        "practitioners.PractitionerProfile",
        on_delete=models.CASCADE,
        related_name="appointments",
    )
    # OneToOne → DB-level uniqueness on slot (NFR-3 / Docs/03).
    slot = models.OneToOneField(
        AvailabilitySlot,
        on_delete=models.PROTECT,
        related_name="appointment",
    )
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.PENDING_PAYMENT,
    )
    cliniko_appointment_id = models.CharField(max_length=128, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "appointment"
        verbose_name_plural = "appointments"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Appointment<{self.pk} {self.status}>"
