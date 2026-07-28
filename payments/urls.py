"""Payment routes under /api/payments/ (Docs/04)."""

from django.urls import path

from payments.views import CreatePaymentIntentView, StripeWebhookView

urlpatterns = [
    path(
        "<int:appointment_id>/create-intent/",
        CreatePaymentIntentView.as_view(),
        name="api_payment_create_intent",
    ),
    path(
        "webhook/stripe/",
        StripeWebhookView.as_view(),
        name="api_payment_stripe_webhook",
    ),
]
