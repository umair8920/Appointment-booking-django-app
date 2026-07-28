"""PMSSyncLog — audit table for Celery sync jobs (Docs/03, 07)."""

from django.db import models


class PMSSyncLog(models.Model):
    class SyncType(models.TextChoices):
        PULL_PRACTITIONERS = "pull_practitioners", "Pull practitioners"
        PULL_AVAILABILITY = "pull_availability", "Pull availability"
        PUSH_APPOINTMENT = "push_appointment", "Push appointment"

    class Status(models.TextChoices):
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    pms_name = models.CharField(max_length=64)
    sync_type = models.CharField(max_length=64, choices=SyncType.choices)
    status = models.CharField(max_length=32, choices=Status.choices)
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "PMS sync log"
        verbose_name_plural = "PMS sync logs"
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return f"PMSSyncLog<{self.pms_name} {self.sync_type} {self.status}>"
