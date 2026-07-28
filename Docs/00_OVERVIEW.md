# 00 — Project Overview

## What this is

A Django-based **appointment booking platform**. Patients book appointments with
practitioners, pay via Stripe, and the platform stays in sync with an external
Practice Management System (PMS) — Cliniko, initially.

This project is being built as a **technical evaluation task** for a software
company assessing: development speed, architectural judgment, and code quality.
This context matters for every decision documented here — **the goal is a
clean, correct, appropriately-scoped implementation, not a feature-maximal
product.**

## Guiding principle

> Build exactly what's required. Design one clean seam for future extension
> (multi-PMS support). Do not build speculative infrastructure for
> requirements that don't exist yet.

Every doc in this folder should be read with that principle as the tiebreaker
whenever a design choice is ambiguous.

## Confirmed technology stack

| Layer | Choice |
|---|---|
| Framework | Django + Django REST Framework (DRF) |
| Database | PostgreSQL |
| Auth | OAuth (via `django-allauth`), both Patients and Practitioners |
| Async tasks | Celery |
| Broker/backend | Redis |
| Payments | Stripe (test mode) |
| External PMS | Cliniko (via an internal adapter interface — see `07`) |

## Confirmed product decisions

- **Both** patients and practitioners authenticate via OAuth. There is no
  separate username/password system to maintain in parallel — see `05` for
  the one exception (allauth still supports normal email/password login as a
  fallback method, but the *mandatory post-signup profile step* applies
  identically regardless of login method).
- After signup (OAuth or normal), the user **must** complete a
  role-appropriate profile form before they can use the rest of the API. This
  is enforced server-side, not just a UI nicety — see `05`.
- Cliniko sync direction: **pull practitioners & availability from Cliniko
  in**, **push confirmed appointments out to Cliniko**. Cliniko is treated as
  the source of truth for scheduling data; this platform is the source of
  truth for the booking/payment transaction itself. See `07`.
- Celery's job in this system is scoped specifically to **Stripe webhook
  processing** and **periodic Cliniko sync** — not a general-purpose task
  queue for unrelated work.

## Document index

| File | Purpose |
|---|---|
| `00_OVERVIEW.md` | This file |
| `01_ARCHITECTURE.md` | App breakdown, layering, request flow |
| `02_REQUIREMENTS.md` | Functional & non-functional requirements |
| `03_DATA_MODELS.md` | Every model, fields, relationships, constraints |
| `04_API_ENDPOINTS.md` | DRF endpoint list and response shapes |
| `05_AUTH_AND_ONBOARDING.md` | OAuth flow, mandatory profile completion |
| `06_INTEGRATIONS_STRIPE_CELERY.md` | Stripe + Celery + Redis, webhook flow |
| `07_INTEGRATIONS_PMS_CLINIKO.md` | PMS adapter interface, Cliniko implementation |
| `08_PROJECT_STRUCTURE.md` | Folder layout, settings structure |
| `09_NON_GOALS_AND_FUTURE_WORK.md` | Explicitly out of scope, and how to extend later |
| `10_UI_AND_TEMPLATES.md` | Demo UI: Django templates, styling, pages, single `web` app |

## Rule for future edits to this doc set

Any change to a model name, app name, field name, or endpoint path **must be
updated in every file that references it**. These docs are meant to be a
single source of truth for AI coding assistants — inconsistency between files
defeats the purpose more than any individual gap in detail would.
