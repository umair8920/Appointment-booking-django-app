# 01 — Architecture

## Style

Single Django project, monolith, multiple apps. No microservices, no
event-sourcing, no CQRS. This is the correct scale for the stated
requirements — see `09_NON_GOALS_AND_FUTURE_WORK.md` for what would justify
revisiting this.

## Apps

| App | Responsibility |
|---|---|
| `accounts` | Custom `User` model, OAuth wiring (allauth), post-signup profile-completion gate |
| `patients` | `PatientProfile` and patient-facing profile logic |
| `practitioners` | `PractitionerProfile`, practitioner-facing profile logic |
| `appointments` | `AvailabilitySlot`, `Appointment`, booking logic, cancellation logic |
| `payments` | `Payment`, Stripe PaymentIntent creation, Stripe webhook endpoint |
| `integrations` | PMS adapter interface (`PMSAdapter`), `cliniko/` implementation, `PMSSyncLog`, Celery tasks for sync |
| `web` | Server-rendered Django templates (demo UI). No models. Calls domain apps' `services.py` directly. See `10_UI_AND_TEMPLATES.md` |

Each app owns its own models, serializers, views, and URLs. No app reaches
into another app's models directly for writes — cross-app interaction goes
through plain Python function calls (service-layer style), not signals,
unless a signal is the clearly correct tool (e.g. auto-creating an empty
profile row on user creation).

## Layering within each app

```
app/
  models.py         # DB schema only, no business logic beyond model-level validation
  serializers.py     # DRF serialization / validation
  services.py         # business logic (booking rules, payment orchestration, etc.)
  views.py            # thin — call services, return serialized response
  urls.py
  tasks.py             # Celery tasks (appointments, payments, integrations only)
```

`services.py` is where the actual logic lives. Views should not contain
business rules — this keeps the API layer replaceable and the logic testable
without spinning up HTTP.

## Request flow — booking an appointment (representative example)

1. Patient hits `POST /api/appointments/` with a slot ID.
2. `appointments` view validates via serializer, calls
   `appointments.services.create_appointment(...)`.
3. Service locks/validates the slot is still open, creates `Appointment`
   with status `pending_payment`.
4. Client then calls `POST /api/payments/{appointment_id}/create-intent/`.
5. `payments` service calls Stripe API, creates a `Payment` row with
   `stripe_payment_intent_id`, returns `client_secret` to frontend.
6. Frontend confirms payment with Stripe directly (standard Stripe Elements
   flow) — this backend never handles raw card data.
7. Stripe sends a webhook to `POST /api/payments/webhook/stripe/`.
8. Webhook view verifies the Stripe signature, immediately enqueues a Celery
   task (`payments.tasks.process_stripe_webhook_event`), returns `200` to
   Stripe right away.
9. Celery task updates `Payment.status`, updates `Appointment.status` to
   `confirmed`, and enqueues `integrations.tasks.push_appointment_to_cliniko`.
10. That task calls the active `PMSAdapter.push_appointment(appointment)`.

This flow is the reference point for `04_API_ENDPOINTS.md`,
`06_INTEGRATIONS_STRIPE_CELERY.md`, and `07_INTEGRATIONS_PMS_CLINIKO.md` —
all three should stay consistent with these exact step names.

## The one deliberate extension point: PMS adapters

```
integrations/
  base.py             # PMSAdapter (ABC) — defines the contract
  cliniko/
    adapter.py         # ClinikoAdapter(PMSAdapter)
    client.py           # thin HTTP client for Cliniko's REST API
    mappers.py           # Cliniko JSON -> internal model fields
  tasks.py               # Celery tasks calling the adapter
  models.py                # PMSSyncLog
```

Internal models (`Practitioner`, `AvailabilitySlot`, `Appointment`) never
contain PMS-specific field names. Any PMS-specific ID is stored as a single
nullable field (e.g. `practitioners.PractitionerProfile.cliniko_practitioner_id`)
— not a generic JSON blob, not a separate polymorphic mapping table. This is
sufficient for "add a second PMS later" — see `07` for why this is enough and
what a second adapter would need to change (answer: nothing outside
`integrations/`).

## What decides "is this extensible enough"

A future developer adding a second PMS (e.g. Acuity) should only need to:
1. Add `integrations/acuity/adapter.py` implementing `PMSAdapter`.
2. Add one settings value to select the active adapter (or a per-practitioner
   field if multiple PMS providers run concurrently — not required today).

They should **not** need to touch `models.py` in `appointments`,
`practitioners`, or `patients`, and should **not** need to change any API
response shape.
