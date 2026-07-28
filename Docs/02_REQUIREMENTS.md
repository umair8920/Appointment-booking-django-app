# 02 — Requirements

Numbered for traceability. Anything not listed here is out of scope unless
added to this file first — see `09_NON_GOALS_AND_FUTURE_WORK.md`.

## Functional requirements

### Auth & onboarding
- FR-1: Users can sign up / log in via OAuth (Google as the initial provider).
- FR-2: Users can also sign up / log in via standard email/password (allauth
  supports this natively — not custom-built).
- FR-3: Every new user has a `role`: `patient` or `practitioner`, selected at
  signup.
- FR-4: After first login, a user **must** complete a role-specific profile
  form before accessing any other endpoint. Enforced by an
  `IsProfileComplete` DRF permission, not just frontend routing.

### Practitioners
- FR-5: Practitioners have a profile (specialization, bio, consultation fee,
  license number).
- FR-6: Practitioners have availability slots, either entered manually or
  synced in from Cliniko.
- FR-7: Patients can list practitioners and view a practitioner's open
  availability slots.

### Patients
- FR-8: Patients have a profile (contact info, DOB, emergency contact).
- FR-9: Patients can book an available slot with a practitioner.
- FR-10: Patients can view and cancel their own upcoming appointments.

### Appointments
- FR-11: Booking a slot creates an `Appointment` in `pending_payment` status
  and marks the slot unavailable to other patients.
- FR-12: An appointment only becomes `confirmed` after Stripe confirms
  successful payment (via webhook, not client-side confirmation).
- FR-13: If payment fails or the client abandons checkout, the slot must be
  released back to availability after a defined timeout (see `06`).
- FR-14: Cancelling a confirmed appointment triggers a Stripe refund
  (test-mode) and releases the slot.

### Payments
- FR-15: Payment is handled entirely through Stripe (test mode). This
  backend never stores raw card data.
- FR-16: A `Payment` record is linked one-to-one with an `Appointment`.
- FR-17: Stripe webhook events are the single source of truth for payment
  status changes.

### PMS integration (Cliniko)
- FR-18: Practitioner and availability data can be pulled in from Cliniko on
  a scheduled basis.
- FR-19: Confirmed appointments are pushed out to Cliniko so the practice's
  existing system stays in sync.
- FR-20: The integration is built behind an adapter interface so a second
  PMS could be added without changing internal models or API responses.

## Non-functional requirements

- NFR-1: PostgreSQL is the only supported database — no SQLite in
  production-shaped code (SQLite is fine for local dev only, and even that is
  discouraged given Postgres-specific constraints may be used).
- NFR-2: Webhook processing must not block the HTTP response to Stripe —
  handled via Celery (see `06`).
- NFR-3: No duplicate bookings of the same slot — enforced at the DB level
  (unique constraint / `select_for_update`), not just application logic.
- NFR-4: Secrets (Stripe keys, OAuth client secrets, Cliniko API key) are
  environment-variable driven, never hardcoded.
- NFR-5: The system should be runnable locally via a documented `docker-compose`
  setup (Postgres, Redis, Django, Celery worker, Celery beat) — this keeps
  the eval reproducible for whoever reviews it.
- NFR-6: Code should be typed where practical and covered by tests for the
  core booking + payment + webhook flow, not exhaustive coverage everywhere.

## Explicitly not required (confirm before adding)

- Multi-tenancy
- SMS/email notification system (may be a nice-to-have — not required by the
  brief; do not build without explicit confirmation)
- Admin-facing analytics/reporting dashboards
- Support for more than one PMS at launch
