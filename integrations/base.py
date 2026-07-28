"""PMS adapter contract (Docs/07)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from appointments.models import Appointment


@dataclass(frozen=True)
class NormalizedPractitioner:
    external_id: str
    first_name: str
    last_name: str
    display_name: str


@dataclass(frozen=True)
class NormalizedSlot:
    external_practitioner_id: str
    start_time: datetime
    end_time: datetime


class PMSAdapter(ABC):
    @abstractmethod
    def fetch_practitioners(self) -> list[NormalizedPractitioner]:
        ...

    @abstractmethod
    def fetch_availability(self, external_practitioner_id: str) -> list[NormalizedSlot]:
        ...

    @abstractmethod
    def push_appointment(self, appointment: Appointment) -> str:
        """Returns the external appointment ID."""
        ...

    @abstractmethod
    def cancel_appointment(self, appointment: Appointment) -> None:
        ...


def get_pms_adapter() -> PMSAdapter:
    """Resolve active adapter from settings.PMS_ADAPTER (Docs/07)."""
    from django.conf import settings
    from django.utils.module_loading import import_string

    return import_string(settings.PMS_ADAPTER)()
