# 09 — Non-Goals & Future Work

This file exists so an AI editor (or a future contributor) doesn't
"helpfully" add infrastructure that wasn't asked for. If you're about to
build something in this list, stop and confirm with the project owner first.

## Explicitly not built now

- **Multi-tenancy.** One deployment, one practice's worth of practitioners.
  No `Organization`/`Tenant` model, no schema-per-tenant.
- **A generic plugin registry for PMS adapters.** One settings value
  (`PMS_ADAPTER`) is enough. Do not build dynamic adapter discovery,
  entry-point scanning, or a `PMSProvider` DB model unless a second PMS is
  actually being added and a concrete need for *runtime-selectable, per-
  practitioner* providers shows up.
- **Custom OAuth implementation.** `django-allauth` already does this
  correctly.
- **A generic background job framework beyond Celery's normal use.** Celery
  is scoped to webhook processing and PMS sync (see `06`). Don't route
  unrelated features through it just because it's already there.
- **Notification system (email/SMS reminders).** Not in the brief. Would be
  a reasonable v2 addition but needs its own scoping conversation — likely
  another Celery beat task plus a `notifications` app, following the same
  patterns already established here.
- **Admin dashboards / reporting.** Django admin (built-in) is sufficient
  for the eval's scope. Don't build custom admin UI.
- **Microservices split.** Nothing here justifies splitting `payments` or
  `integrations` into a separate service. Revisit only if a genuinely
  separate scaling or deployment need appears — not preemptively.
- **Generic JSON blob storage for PMS-specific data.** The adapter pattern
  in `07` is the extensibility answer. A catch-all `extra_data = JSONField()`
  on shared models would undermine the whole point of normalizing PMS data
  and should not be added as a shortcut.

## Reasonable future additions (not built now, but the structure already accommodates them)

- **A second PMS provider** — see `07` for exactly what this requires. The
  structure already supports it without modification to core apps.
- **A second OAuth provider** (Microsoft, Apple, etc.) — config-level change
  via allauth, see `05`.
- **Recurring appointments** — would extend `appointments.services`, likely
  adding a `RecurrenceRule` model linked to `AvailabilitySlot` generation.
  Not built now because it's not in the brief.
- **Waitlists for fully-booked practitioners** — a plausible `appointments`
  addition, not built now.
- **Practitioner-side calendar view / bulk availability management UI** —
  frontend concern, backend already exposes what's needed via
  `/api/practitioners/{id}/availability/`.

## The test for "should this be added now"

Before adding anything not in `02_REQUIREMENTS.md`, ask:
1. Is it explicitly required by the brief?
2. If not, does skipping it break something that *is* required?

If both answers are no, it belongs in this file as a future note, not in the
codebase.
