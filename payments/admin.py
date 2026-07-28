from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "appointment",
        "amount",
        "currency",
        "status",
        "stripe_payment_intent_id",
        "created_at",
    )
    list_filter = ("status", "currency")
    search_fields = ("stripe_payment_intent_id",)
    raw_id_fields = ("appointment",)
