# 04 — API Endpoints

Base prefix: `/api/`. All endpoints (except the Stripe webhook and OAuth
entry points) require authentication. Endpoints other than
`complete-profile/` also require `is_profile_complete = True` (enforced by
the `IsProfileComplete` permission — see `05`).

## Auth (`accounts` app, backed by allauth / dj-rest-auth)

| Method | Path | Purpose | Auth required |
|---|---|---|---|
| `POST` | `/api/auth/signup/` | Email/password signup, sets `role` | No |
| `POST` | `/api/auth/login/` | Email/password login | No |
| `GET`/`POST` | `/api/auth/google/` | OAuth entry (allauth-provided) | No |
| `POST` | `/api/auth/logout/` | Logout | Yes |
| `GET` | `/api/auth/me/` | Current user + `role` + `is_profile_complete` | Yes |
| `POST` | `/api/auth/complete-profile/` | Submit role-specific profile form | Yes (profile-complete check bypassed here) |

## Practitioners (`practitioners` app)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/practitioners/` | List practitioners |
| `GET` | `/api/practitioners/{id}/` | Practitioner detail |
| `GET` | `/api/practitioners/{id}/availability/` | Open slots for that practitioner |
| `PATCH` | `/api/practitioners/me/` | Practitioner updates own profile |

## Patients (`patients` app)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/patients/me/` | Own profile |
| `PATCH` | `/api/patients/me/` | Update own profile |

## Appointments (`appointments` app)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/appointments/` | List own appointments (role-scoped: patient sees own bookings, practitioner sees own schedule) |
| `POST` | `/api/appointments/` | Book a slot → creates `Appointment` with status `pending_payment` |
| `GET` | `/api/appointments/{id}/` | Detail |
| `POST` | `/api/appointments/{id}/cancel/` | Cancel → triggers refund via `payments` service |

## Payments (`payments` app)

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/payments/{appointment_id}/create-intent/` | Creates Stripe PaymentIntent, returns `client_secret` |
| `POST` | `/api/payments/webhook/stripe/` | Stripe webhook receiver. No user auth — verified via Stripe signature header instead |

## Response shape conventions

- All list endpoints are paginated (DRF `PageNumberPagination`, default page
  size 20).
- All error responses follow DRF's default `{"detail": "..."}` or field-level
  validation error shape — no custom error envelope layered on top.
- Timestamps are ISO 8601, timezone-aware, UTC.
- **Nothing in these response shapes ever exposes raw Cliniko (or any PMS)
  field names.** Practitioner/availability responses always use the internal
  model's field names from `03_DATA_MODELS.md`, regardless of whether that
  data originated locally or was synced in — this is the whole point of the
  adapter layer in `07`.

## Example: `GET /api/practitioners/{id}/availability/`

```json
{
  "count": 2,
  "results": [
    {
      "id": 14,
      "start_time": "2026-08-01T09:00:00Z",
      "end_time": "2026-08-01T09:30:00Z",
      "is_booked": false
    },
    {
      "id": 15,
      "start_time": "2026-08-01T09:30:00Z",
      "end_time": "2026-08-01T10:00:00Z",
      "is_booked": false
    }
  ]
}
```

This shape is identical whether the slot's `source` is `manual` or
`cliniko`.
