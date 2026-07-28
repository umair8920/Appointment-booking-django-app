# 08 — Project Structure

```
project_root/
├── manage.py
├── requirements.txt
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── docs/                          # this documentation set
├── config/                        # Django project package (settings, root urls, celery app)
│   ├── __init__.py                # imports celery app so `@shared_task` works
│   ├── settings/
│   │   ├── base.py
│   │   ├── local.py
│   │   └── production.py
│   ├── celery.py                  # Celery app instance + beat schedule
│   ├── urls.py                    # root URLconf, includes each app's urls under /api/
│   └── wsgi.py / asgi.py
│
├── accounts/
│   ├── models.py                  # User
│   ├── serializers.py
│   ├── views.py
│   ├── permissions.py             # IsProfileComplete
│   ├── signals.py                 # creates empty profile row on user creation
│   └── urls.py
│
├── patients/
│   ├── models.py                  # PatientProfile
│   ├── serializers.py
│   ├── views.py
│   └── urls.py
│
├── practitioners/
│   ├── models.py                  # PractitionerProfile
│   ├── serializers.py
│   ├── views.py
│   └── urls.py
│
├── appointments/
│   ├── models.py                  # AvailabilitySlot, Appointment
│   ├── serializers.py
│   ├── services.py                # booking, cancellation logic
│   ├── views.py
│   ├── tasks.py                   # release_stale_pending_appointments
│   └── urls.py
│
├── payments/
│   ├── models.py                  # Payment
│   ├── serializers.py
│   ├── services.py                # Stripe PaymentIntent creation, refunds
│   ├── views.py                   # includes webhook receiver
│   ├── tasks.py                   # process_stripe_webhook_event
│   └── urls.py
│
├── integrations/
│   ├── base.py                    # PMSAdapter ABC, NormalizedPractitioner, NormalizedSlot
│   ├── models.py                  # PMSSyncLog
│   ├── tasks.py                   # sync_cliniko_practitioners, sync_cliniko_availability, push_appointment_to_cliniko
│   └── cliniko/
│       ├── client.py
│       ├── mappers.py
│       └── adapter.py
│
├── web/
│   ├── templates/                 # base.html + all demo UI pages, see 10_UI_AND_TEMPLATES.md
│   ├── static/web/                # base.css, checkout.js
│   ├── views.py
│   └── urls.py                    # mounted at '/', separate from '/api/'
│
└── tests/
    ├── test_booking_flow.py
    ├── test_payment_webhook.py
    └── test_cliniko_adapter.py
```

## Settings split rationale

`base.py` / `local.py` / `production.py` is the standard, minimal split —
enough to keep dev and prod config from tangling, without a full
django-environ-style config framework unless the team already uses one.
`.env` values are read via `os.environ` (or `django-environ`, either is
fine) in all environments.

## Where tests live

Flat `tests/` at the project root for the core cross-cutting flows (booking →
payment → webhook → Cliniko push), since that flow spans multiple apps and
doesn't belong to any single one. Per-app unit tests (model validation,
serializer validation) can live in each app's own `tests.py` — both patterns
are fine; don't force everything into one style if it doesn't fit.
