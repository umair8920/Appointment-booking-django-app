# 03 — Data Models

Field lists here are the contract. If an AI editor needs a field not listed
here, add it to this file in the same change — don't invent fields silently.

## `accounts.User` (custom user model, extends `AbstractUser`)

| Field | Type | Notes |
|---|---|---|
| `email` | `EmailField`, unique | used as `USERNAME_FIELD` |
| `role` | `CharField`, choices: `patient`, `practitioner` | set at signup, immutable after |
| `is_profile_complete` | `BooleanField`, default `False` | flips to `True` once role profile form is submitted |

allauth's social account tables handle OAuth provider linkage — not
duplicated here.

## `patients.PatientProfile`

| Field | Type | Notes |
|---|---|---|
| `user` | `OneToOneField(User)` | |
| `date_of_birth` | `DateField` | |
| `phone_number` | `CharField` | |
| `address` | `TextField` | |
| `emergency_contact_name` | `CharField` | |
| `emergency_contact_phone` | `CharField` | |

## `practitioners.PractitionerProfile`

| Field | Type | Notes |
|---|---|---|
| `user` | `OneToOneField(User)` | |
| `specialization` | `CharField` | |
| `bio` | `TextField` | |
| `license_number` | `CharField` | |
| `consultation_fee` | `DecimalField` | in the platform's base currency |
| `cliniko_practitioner_id` | `CharField`, null=True, blank=True | external mapping, single nullable field — see `01` |

## `appointments.AvailabilitySlot`

| Field | Type | Notes |
|---|---|---|
| `practitioner` | `ForeignKey(PractitionerProfile)` | |
| `start_time` | `DateTimeField` | timezone-aware |
| `end_time` | `DateTimeField` | |
| `is_booked` | `BooleanField`, default `False` | |
| `source` | `CharField`, choices: `manual`, `cliniko` | where the slot originated |

Constraint: unique-together on (`practitioner`, `start_time`) to prevent
duplicate slot creation from sync jobs.

## `appointments.Appointment`

| Field | Type | Notes |
|---|---|---|
| `patient` | `ForeignKey(PatientProfile)` | |
| `practitioner` | `ForeignKey(PractitionerProfile)` | |
| `slot` | `OneToOneField(AvailabilitySlot)` | one appointment per slot |
| `status` | `CharField`, choices: `pending_payment`, `confirmed`, `cancelled`, `completed` | |
| `cliniko_appointment_id` | `CharField`, null=True, blank=True | set after successful push |
| `created_at` | `DateTimeField(auto_now_add=True)` | |

Constraint: DB-level uniqueness on `slot` (via the `OneToOneField`) is what
actually prevents double-booking — this is enforced at the database, not
just checked in application code (NFR-3 in `02`).

## `payments.Payment`

| Field | Type | Notes |
|---|---|---|
| `appointment` | `OneToOneField(Appointment)` | |
| `stripe_payment_intent_id` | `CharField`, unique | |
| `amount` | `DecimalField` | |
| `currency` | `CharField`, default `usd` | |
| `status` | `CharField`, choices: `pending`, `succeeded`, `failed`, `refunded` | mirrors Stripe's PaymentIntent status vocabulary, kept intentionally small |
| `created_at` | `DateTimeField(auto_now_add=True)` | |
| `updated_at` | `DateTimeField(auto_now=True)` | |

## `integrations.PMSSyncLog`

| Field | Type | Notes |
|---|---|---|
| `pms_name` | `CharField` | e.g. `cliniko` |
| `sync_type` | `CharField`, choices: `pull_practitioners`, `pull_availability`, `push_appointment` | |
| `status` | `CharField`, choices: `success`, `failed` | |
| `started_at` | `DateTimeField` | |
| `finished_at` | `DateTimeField`, null=True | |
| `error_message` | `TextField`, blank=True | |

This is a plain audit table, not part of the adapter contract itself — it
exists so sync failures are observable, which is a reasonable minimum for
anything running on Celery beat unattended.

## Relationships at a glance

```
User (1) --- (1) PatientProfile
User (1) --- (1) PractitionerProfile
PractitionerProfile (1) --- (*) AvailabilitySlot
AvailabilitySlot (1) --- (1) Appointment
PatientProfile (1) --- (*) Appointment
PractitionerProfile (1) --- (*) Appointment
Appointment (1) --- (1) Payment
```
