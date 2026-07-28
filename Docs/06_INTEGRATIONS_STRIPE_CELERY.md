# 06 — Stripe + Celery + Redis

## Stripe (test mode)

- Test-mode API keys only (`sk_test_...` / `pk_test_...`), stored via
  environment variables (`STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`,
  `STRIPE_WEBHOOK_SECRET`) — never committed.
- This backend only ever creates a **PaymentIntent** server-side
  (`POST /api/payments/{appointment_id}/create-intent/`) and returns its
  `client_secret`. Card entry and payment confirmation happen client-side via
  Stripe Elements/Payment Element — raw card data never touches this backend.
  This is a security requirement, not a style preference.

## Why Celery is used, specifically

Celery's role in this system is **narrow and specific**: processing Stripe
webhook events asynchronously, plus periodic Cliniko sync jobs (via Celery
beat — see `07`). It is not used as a general background-job dumping ground
for unrelated work. If a future requirement needs background processing
outside these two use cases, that's a deliberate decision to make at that
time, not something to default into now.

## Webhook flow (the actual reason Celery exists here)

1. Stripe sends an event to `POST /api/payments/webhook/stripe/`.
2. The view's **only** job:
   - Verify the `Stripe-Signature` header against `STRIPE_WEBHOOK_SECRET`.
   - If invalid → `400`, nothing enqueued.
   - If valid → enqueue `payments.tasks.process_stripe_webhook_event(event_data)`
     and immediately return `200`.
3. The view does **not** touch the database. This is the entire reason for
   using Celery here: Stripe expects a fast response, and DB work (updating
   `Payment`, `Appointment`, potentially calling out to Cliniko) should not
   happen inside that response cycle.
4. `process_stripe_webhook_event` (Celery task):
   - Handles `payment_intent.succeeded` → sets `Payment.status = succeeded`,
     `Appointment.status = confirmed`, enqueues
     `integrations.tasks.push_appointment_to_cliniko`.
   - Handles `payment_intent.payment_failed` → sets `Payment.status = failed`,
     releases the slot (`AvailabilitySlot.is_booked = False`), leaves
     `Appointment.status` as `cancelled`.
   - Handles `charge.refunded` → sets `Payment.status = refunded`.
   - Task is idempotent: re-processing the same `stripe_payment_intent_id`
     with the same target status is a no-op, since Stripe may redeliver
     webhook events (Stripe's own retry behavior — this is a correctness
     requirement, not optional hardening).

## Abandoned checkout / expired pending appointments

- A slot booked but never paid for should not stay locked forever.
- Celery beat runs `appointments.tasks.release_stale_pending_appointments`
  on a schedule (e.g. every 5 minutes), which cancels any `Appointment` still
  in `pending_payment` after a defined timeout (e.g. 15 minutes) and releases
  its slot. This directly satisfies FR-13 in `02_REQUIREMENTS.md`.

## Redis

- Single Redis instance serves as both Celery broker and result backend for
  local/eval purposes. No separate broker/backend split — that's an
  optimization for a scale this project doesn't need.
- Config lives in `settings.py` via `CELERY_BROKER_URL` /
  `CELERY_RESULT_BACKEND`, both environment-variable driven.

## Celery task inventory (for reference — full list, kept here so it's not
duplicated inconsistently elsewhere)

| Task | Trigger | App |
|---|---|---|
| `process_stripe_webhook_event` | Webhook view | `payments` |
| `release_stale_pending_appointments` | Celery beat, every 5 min | `appointments` |
| `sync_cliniko_practitioners` | Celery beat, e.g. hourly | `integrations` |
| `sync_cliniko_availability` | Celery beat, e.g. every 15 min | `integrations` |
| `push_appointment_to_cliniko` | Triggered by webhook task on payment success | `integrations` |
