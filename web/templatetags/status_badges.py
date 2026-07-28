"""Appointment status → Bootstrap badge classes (Docs/10)."""

from django import template

register = template.Library()

STATUS_BADGE_CLASSES = {
    "pending_payment": "bg-secondary",
    "confirmed": "bg-success",
    "cancelled": "bg-danger",
    "completed": "bg-primary",
}


@register.simple_tag
def status_badge_class(status: str) -> str:
    return STATUS_BADGE_CLASSES.get(status, "bg-secondary")
