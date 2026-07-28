# 05 — Auth & Onboarding

## Library choice

`django-allauth` (+ `dj-rest-auth` for DRF-friendly token/session endpoints
on top of it). Do not hand-roll OAuth token exchange — allauth already
handles Google OAuth correctly and is the standard, well-audited choice for
this. Custom OAuth implementation would be the textbook overengineering
mistake here.

## Why both OAuth and email/password exist

The brief requires OAuth. allauth supports email/password natively as part
of the same system with no extra work, so it's left enabled rather than
artificially disabled — but **OAuth is the primary, expected path** and
nothing in the product design treats email/password as a second-class
citizen. Both converge on the exact same onboarding gate below.

## Signup flow

1. User signs up via Google OAuth or email/password.
2. On first login, `role` is captured (`patient` or `practitioner`) —
   presented as a required choice immediately after auth completes, before
   any other action is possible.
3. `User.is_profile_complete` defaults to `False`.
4. A corresponding empty `PatientProfile` or `PractitionerProfile` row is
   created automatically (via a `post_save` signal on `User`, scoped only to
   this — not a general signals-everywhere pattern).

## The mandatory profile-completion gate

- A custom DRF permission class, `IsProfileComplete`, is applied as a default
  permission (alongside `IsAuthenticated`) on every viewset **except**:
  - `accounts` auth endpoints themselves
  - `POST /api/auth/complete-profile/`
- If `is_profile_complete` is `False`, every other endpoint returns `403`
  with a clear `{"detail": "Profile completion required."}` body, so the
  frontend can redirect to the profile form deterministically.
- `POST /api/auth/complete-profile/` accepts the role-specific fields (see
  `03_DATA_MODELS.md` for exact fields per role), validates them, saves to
  the appropriate profile model, and sets `is_profile_complete = True` in the
  same transaction.

This is enforced server-side specifically because the brief calls it
**necessary to proceed** — a frontend-only gate would not satisfy that.

## Session vs token auth (finalized)

- **The demo UI (`web` app, see `10_UI_AND_TEMPLATES.md`) uses standard
  Django session auth**, via allauth's own redirect-based login/signup/
  Google OAuth views. This is the only auth mechanism the UI needs.
- **Token/JWT auth (via `dj-rest-auth`) is reserved for non-browser API
  consumers** — i.e. anyone calling `/api/` directly outside the `web` app
  (future mobile client, external integration, Postman/curl during review).
  Both mechanisms can be enabled simultaneously in DRF's
  `DEFAULT_AUTHENTICATION_CLASSES` without conflict; each request just uses
  whichever credential it presents.
- No separate decision needed later — this was the one open item in this
  file and it's closed by the UI app's existence.

## Provider extensibility (not just PMS)

Because allauth's provider system is itself a plugin architecture, adding a
second OAuth provider later (e.g. Microsoft, Apple) is a config change in
`settings.py` plus a new provider app — not a structural change. Worth
noting so nobody re-invents this: OAuth provider extensibility comes for
free from the library choice, unlike PMS extensibility which we build
ourselves (see `07`).
