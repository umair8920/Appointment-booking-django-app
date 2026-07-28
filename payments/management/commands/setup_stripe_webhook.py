"""
Create / list Stripe webhook endpoints for this project's Stripe account.

Usage:
  python manage.py setup_stripe_webhook
  python manage.py setup_stripe_webhook --url https://your-public-host/api/payments/webhook/stripe/

Local sandbox (recommended while developing):
  tools\\stripe\\stripe.exe listen --api-key %STRIPE_SECRET_KEY% ^
    --forward-to localhost:8000/api/payments/webhook/stripe/ ^
    --events payment_intent.succeeded,payment_intent.payment_failed,charge.refunded

Copy the printed whsec_... into .env as STRIPE_WEBHOOK_SECRET.
"""

from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

import stripe

REQUIRED_EVENTS = [
    "payment_intent.succeeded",
    "payment_intent.payment_failed",
    "charge.refunded",
]


class Command(BaseCommand):
    help = "List or create the Stripe webhook endpoint for /api/payments/webhook/stripe/"

    def add_arguments(self, parser):
        parser.add_argument(
            "--url",
            default="",
            help=(
                "Public HTTPS URL for the webhook. Required to create a Dashboard "
                "endpoint. Localhost is not accepted by Stripe — use stripe listen."
            ),
        )
        parser.add_argument(
            "--create",
            action="store_true",
            help="Create the endpoint when --url is a public HTTPS URL.",
        )

    def handle(self, *args, **options):
        secret = settings.STRIPE_SECRET_KEY
        if not secret or secret.endswith("replace_me"):
            raise CommandError("STRIPE_SECRET_KEY is not configured in .env")

        stripe.api_key = secret
        endpoints = stripe.WebhookEndpoint.list(limit=100)
        self.stdout.write(self.style.NOTICE(f"Existing webhook endpoints: {len(endpoints.data)}"))
        for ep in endpoints.data:
            self.stdout.write(f"  - {ep.id}  status={ep.status}  url={ep.url}")
            self.stdout.write(f"    events={list(ep.enabled_events)}")

        url = (options.get("url") or "").strip()
        if not options.get("create"):
            self.stdout.write("")
            self.stdout.write(
                "Local dev: run tools\\stripe\\stripe.exe listen "
                "--forward-to localhost:8000/api/payments/webhook/stripe/ "
                "--events payment_intent.succeeded,payment_intent.payment_failed,charge.refunded"
            )
            self.stdout.write(
                "Then set STRIPE_WEBHOOK_SECRET=whsec_... from the CLI output."
            )
            return

        if not url:
            raise CommandError("--create requires --url https://...")
        if url.startswith("http://localhost") or url.startswith("http://127."):
            raise CommandError(
                "Stripe Dashboard webhooks require a public HTTPS URL. "
                "For local development use `stripe listen` instead."
            )

        existing = next((e for e in endpoints.data if e.url == url), None)
        if existing:
            self.stdout.write(self.style.WARNING(f"Endpoint already exists: {existing.id}"))
            self.stdout.write(
                "Retrieve the signing secret from Stripe Dashboard → Developers → Webhooks."
            )
            return

        created = stripe.WebhookEndpoint.create(
            url=url,
            enabled_events=REQUIRED_EVENTS,
            description="ClinicBook appointment payments (Docs/06)",
        )
        self.stdout.write(self.style.SUCCESS(f"Created webhook endpoint: {created.id}"))
        secret_value = getattr(created, "secret", None)
        if secret_value:
            self.stdout.write(
                self.style.WARNING(
                    "Copy this signing secret into .env as STRIPE_WEBHOOK_SECRET "
                    "(shown only once):"
                )
            )
            self.stdout.write(secret_value)
        else:
            self.stdout.write(
                "Open Stripe Dashboard → Webhooks to copy the signing secret into .env."
            )
