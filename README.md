# Local stack (NFR-5) — requires Docker Desktop / Docker Engine
#
#   docker compose up --build
#
# Services:
#   web     http://localhost:8000
#   db      postgres://postgres:postgres@localhost:5432/appointment_booking
#   redis   redis://localhost:6379/0
#   worker  Celery worker
#   beat    Celery beat
#
# Copy .env.example → .env and fill Stripe / OAuth / Cliniko secrets first.
#
# Without Docker (current Windows host setup):
#   1. Activate venv
#   2. Ensure Postgres + Redis (Memurai) are running
#   3. python manage.py migrate
#   4. python manage.py runserver
#   5. celery -A config worker -l info
#   6. celery -A config beat -l info
#   7. (optional) powershell -File scripts\stripe_listen.ps1
#
# Demo UI (Milestone 8 — Docs/10): http://localhost:8000
#   signup/login → complete profile → practitioners → book slot → Stripe checkout
#   patient: /my-appointments/   practitioner: /my-schedule/
#
# Tests:
#   python manage.py test
