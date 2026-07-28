"""Celery tasks for Cliniko pull/push sync (Docs/06, 07)."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="integrations.tasks.push_appointment_to_cliniko")
def push_appointment_to_cliniko(appointment_id: int) -> None:
    """
    Push a confirmed appointment to the active PMS adapter (Docs/07).

    Full ClinikoAdapter implementation lands in Milestone 6; this task is
    registered now so payment-success webhooks can enqueue it (Docs/06).
    """
    logger.info(
        "push_appointment_to_cliniko(%s) queued — Cliniko adapter in Milestone 6.",
        appointment_id,
    )


@shared_task(name="integrations.tasks.sync_cliniko_practitioners")
def sync_cliniko_practitioners() -> None:
    """Pull practitioners from Cliniko — Milestone 6."""
    logger.info("sync_cliniko_practitioners stub — implemented in Milestone 6.")


@shared_task(name="integrations.tasks.sync_cliniko_availability")
def sync_cliniko_availability() -> None:
    """Pull availability from Cliniko — Milestone 6."""
    logger.info("sync_cliniko_availability stub — implemented in Milestone 6.")
