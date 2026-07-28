# 07 — PMS Integration (Cliniko, and future PMS providers)

## Sync direction (confirmed default)

- **Pull in**: practitioners and availability slots, from Cliniko →
  this platform. Cliniko is treated as the source of truth for who the
  practitioners are and when they're free.
- **Push out**: confirmed appointments, from this platform → Cliniko, after
  Stripe payment succeeds. This platform is the source of truth for the
  booking + payment transaction itself.

This is a deliberate choice, not an accident of "whatever's easier": a real
practice already runs its calendar in Cliniko day-to-day, so pulling
availability respects that. But the booking + payment transaction is this
platform's job, so pushing the *result* of that transaction back to Cliniko
keeps the practice's own system accurate without this platform trying to
own scheduling logic that already lives elsewhere.

## The adapter contract

```python
# integrations/base.py
from abc import ABC, abstractmethod

class PMSAdapter(ABC):
    @abstractmethod
    def fetch_practitioners(self) -> list[NormalizedPractitioner]:
        ...

    @abstractmethod
    def fetch_availability(self, external_practitioner_id: str) -> list[NormalizedSlot]:
        ...

    @abstractmethod
    def push_appointment(self, appointment: "Appointment") -> str:
        """Returns the external appointment ID."""
        ...

    @abstractmethod
    def cancel_appointment(self, appointment: "Appointment") -> None:
        ...
```

`NormalizedPractitioner` and `NormalizedSlot` are simple dataclasses defined
in `integrations/base.py` — they exist so mapping logic lives entirely
inside the adapter (`cliniko/mappers.py`), and nothing outside
`integrations/` ever sees a raw Cliniko JSON key.

## `ClinikoAdapter`

```
integrations/cliniko/
  client.py     # thin wrapper over Cliniko's REST API (auth, pagination, rate limits)
  mappers.py     # Cliniko JSON -> NormalizedPractitioner / NormalizedSlot
  adapter.py       # ClinikoAdapter(PMSAdapter), uses client.py + mappers.py
```

- `client.py` handles only HTTP concerns: auth header, base URL, pagination,
  basic retry on transient failures. No business logic.
- `mappers.py` is where Cliniko's specific field names get translated —
  this is the **only** place in the codebase allowed to know what Cliniko's
  response JSON looks like.
- `adapter.py` orchestrates: calls `client.py`, passes results through
  `mappers.py`, returns normalized objects to the calling Celery task.

## How sync jobs use this

- `integrations.tasks.sync_cliniko_practitioners`: calls
  `ClinikoAdapter().fetch_practitioners()`, upserts into
  `PractitionerProfile` (matched via `cliniko_practitioner_id`), logs result
  to `PMSSyncLog`.
- `integrations.tasks.sync_cliniko_availability`: same pattern, for
  `AvailabilitySlot` (matched via `practitioner` + `start_time`, with
  `source='cliniko'`).
- `integrations.tasks.push_appointment_to_cliniko`: calls
  `ClinikoAdapter().push_appointment(appointment)`, stores the returned ID in
  `Appointment.cliniko_appointment_id`, logs result.

Which adapter is "active" is a single settings value
(`PMS_ADAPTER = "integrations.cliniko.adapter.ClinikoAdapter"`), resolved via
Django's standard import-string pattern — the same mechanism Django itself
uses for things like `AUTH_USER_MODEL` swapping. No custom plugin registry
needed.

## What adding a second PMS actually requires (concrete test of "extensible enough")

To add, say, an `AcuityAdapter` later:
1. Create `integrations/acuity/{client,mappers,adapter}.py` implementing
   `PMSAdapter`.
2. Point `PMS_ADAPTER` at it (or, if multiple PMS providers must run
   concurrently per-practitioner, add one nullable field like
   `PractitionerProfile.pms_provider` — not required today, noted here only
   so it's clear the model already has room for it without restructuring).
3. Nothing in `appointments`, `patients`, `practitioners`, or any DRF
   serializer changes. Nothing in `04_API_ENDPOINTS.md`'s response shapes
   changes.

If a proposed change would require touching those other apps, that's a sign
the adapter boundary is being violated somewhere and should be corrected
before merging — not a sign the boundary needs to be redesigned.
