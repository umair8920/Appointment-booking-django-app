# 10 — UI (Django Templates, Single App)

## Why this approach

The brief needs a **demo surface for evaluators to click through**, not a
product-grade frontend. Building a separate React/Vue app would double the
work (two auth flows, two deployments, CORS config, a build pipeline) for no
requirement that asks for it — that's exactly the overengineering this
project is avoiding elsewhere. So: **server-rendered Django templates,
inside the existing project, in one dedicated app.**

## The app: `web`

```
web/
  templates/
    web/
      base.html                 # shared layout: nav, header, footer, CSS/JS includes
      home.html                  # landing page
      complete_profile.html       # role-specific profile form (patient / practitioner variants via {% if %})
      practitioner_list.html
      practitioner_detail.html      # profile + availability slots
      booking_checkout.html          # Stripe Elements payment page
      my_appointments.html            # patient view
      my_schedule.html                 # practitioner view
    account/                            # allauth template overrides (login, signup, google OAuth)
      login.html
      signup.html
  static/
    web/
      css/
        base.css                  # theme variables + minimal custom rules
      js/
        checkout.js                 # Stripe Elements mounting + confirm payment
  views.py                          # Django CBVs/FBVs, call into domain services directly
  urls.py                            # mounted at '' (root), separate from /api/
```

This app has **no models of its own**. It's a presentation layer over the
same `services.py` functions and models already defined in `accounts`,
`patients`, `practitioners`, `appointments`, and `payments`. It does not
duplicate business logic, and it does not call the DRF API over HTTP from
the server side — Python function calls directly, same process. The one
exception is Stripe payment confirmation, which is inherently client-side JS
(Stripe Elements can't run server-side) and talks to the existing
`/api/payments/...` endpoints via `fetch()`.

## Auth for the UI (this finalizes the open question in `05`)

- **The `web` app uses session auth**, via allauth's own server-rendered
  login/signup/Google-OAuth views — this is allauth's default, redirect-based
  flow, and it's what template-based pages should use. No JWT/token handling
  in the browser for this UI.
- Token/JWT auth (from `05`) is reserved for non-browser API consumers only
  (e.g. if a future mobile app or external integration calls `/api/`
  directly). The demo UI never needs it.
- Profile-completion enforcement for the UI is a small `LoginRequiredMixin`-
  style mixin (`ProfileCompleteRequiredMixin`) that redirects to
  `complete_profile.html` instead of returning a `403` — same underlying
  check (`User.is_profile_complete`) as the API's `IsProfileComplete`
  permission in `05`, just a redirect instead of a JSON error.

## Page list and what each one demonstrates

| Page | Path | Demonstrates |
|---|---|---|
| Home / landing | `/` | Entry point, login/signup links |
| Login / Signup | `/accounts/login/`, `/accounts/signup/` (allauth) | Email/password + Google OAuth |
| Complete profile | `/complete-profile/` | Mandatory onboarding gate (FR-4) |
| Practitioner list | `/practitioners/` | Listing, pulled-in Cliniko data rendering identically to manual data |
| Practitioner detail | `/practitioners/<id>/` | Availability slots, booking entry point |
| Booking checkout | `/appointments/book/<slot_id>/` | Stripe PaymentIntent + Elements confirmation |
| My appointments | `/my-appointments/` | Patient booking history, cancel action |
| My schedule | `/my-schedule/` | Practitioner-side view of booked appointments |

No page here isn't traceable to a functional requirement in
`02_REQUIREMENTS.md` — this list should stay in sync with that file.

## Styling approach

- **Bootstrap 5 via CDN** in `base.html` — no build step, no Node/webpack,
  no npm dependency in the Django project. This is the correct "boring and
  fast" choice for a demo UI; a bundler would be actual overengineering here.
- A single `base.css` on top of Bootstrap, defining theme via CSS custom
  properties, so the whole UI stays visually consistent without page-by-page
  styling decisions:

```css
:root {
  --color-primary: #2563eb;
  --color-primary-dark: #1d4ed8;
  --color-bg: #f8fafc;
  --color-surface: #ffffff;
  --color-text: #1e293b;
  --color-text-muted: #64748b;
  --color-success: #16a34a;
  --color-danger: #dc2626;
  --radius: 8px;
  --font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
}

body {
  background-color: var(--color-bg);
  color: var(--color-text);
  font-family: var(--font-family);
}

.card, .btn-primary, .navbar {
  border-radius: var(--radius);
}

.btn-primary {
  background-color: var(--color-primary);
  border-color: var(--color-primary);
}
.btn-primary:hover {
  background-color: var(--color-primary-dark);
}
```

- Every template extends `base.html` and uses standard Bootstrap components
  (navbar, cards, forms, badges for appointment status) — no custom
  component library, no design system beyond these variables.
- Status badges use a consistent mapping everywhere they appear (appointment
  list, schedule view): `pending_payment` = gray, `confirmed` = green,
  `cancelled` = red, `completed` = blue. Defined once as a template filter
  (`web/templatetags/status_badges.py`), not re-implemented per template.

## JS scope

Minimal, vanilla JS only:
- `checkout.js`: mounts Stripe Elements, calls
  `POST /api/payments/{appointment_id}/create-intent/` via `fetch`, confirms
  payment with Stripe.js, redirects to `my_appointments.html` on success.
- No frontend framework, no state management library, no client-side
  routing. Every other page is a plain server-rendered GET/POST form.

## What this explicitly is not

- Not a replacement for the DRF API — `/api/` still exists, still fully
  functional, and is what any real frontend or mobile client would use
  later. `web` is a thin demo/admin-adjacent surface, not the "real" client.
- Not responsive-design-polished or accessibility-audited beyond what
  Bootstrap gives for free. Fine for a demo; would need explicit scoping to
  harden further.
- Not styled per-practitioner/brandable — one fixed theme, no white-labeling.
