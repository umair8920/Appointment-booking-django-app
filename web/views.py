"""
Demo UI views — call domain services/models directly (Docs/10).

No DRF HTTP from the server. Stripe Elements uses fetch() to /api/payments/...
"""

from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Sum
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.generic import DetailView, ListView, TemplateView
from rest_framework.exceptions import ValidationError as DRFValidationError

from accounts.models import User
from accounts.services import complete_user_profile
from appointments.models import Appointment, AvailabilitySlot
from appointments.services import (
    cancel_appointment,
    create_appointment,
    create_availability_slot,
    delete_availability_slot,
)
from payments.models import Payment
from practitioners.models import PractitionerProfile
from web.forms import AvailabilitySlotForm, CompleteProfileForm
from web.mixins import ProfileCompleteRequiredMixin, StaffRequiredMixin


class HomeView(TemplateView):
    template_name = "web/home.html"


class CompleteProfileView(LoginRequiredMixin, View):
    login_url = reverse_lazy("account_login")
    template_name = "web/complete_profile.html"

    def get(self, request):
        if request.user.is_profile_complete:
            return redirect("home")
        form = CompleteProfileForm(user=request.user)
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        if request.user.is_profile_complete:
            return redirect("home")
        form = CompleteProfileForm(request.POST, user=request.user)
        if form.is_valid():
            complete_user_profile(request.user, form.cleaned_data)
            messages.success(request, "Profile completed. You're ready to go.")
            return redirect("practitioner_list")
        return render(request, self.template_name, {"form": form})


class PractitionerListView(ProfileCompleteRequiredMixin, ListView):
    template_name = "web/practitioner_list.html"
    context_object_name = "practitioners"

    def get_queryset(self):
        return (
            PractitionerProfile.objects.filter(
                user__role=User.Role.PRACTITIONER,
                user__is_profile_complete=True,
            )
            .select_related("user")
            .order_by("specialization", "id")
        )


class PractitionerDetailView(ProfileCompleteRequiredMixin, DetailView):
    template_name = "web/practitioner_detail.html"
    context_object_name = "practitioner"
    pk_url_kwarg = "pk"

    def get_queryset(self):
        return PractitionerProfile.objects.filter(
            user__role=User.Role.PRACTITIONER,
            user__is_profile_complete=True,
        ).select_related("user")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["open_slots"] = AvailabilitySlot.objects.filter(
            practitioner=self.object,
            is_booked=False,
        ).order_by("start_time")
        return ctx


class BookingCheckoutView(ProfileCompleteRequiredMixin, View):
    """Book slot (service) then render Stripe Elements checkout (Docs/10)."""

    template_name = "web/booking_checkout.html"

    @method_decorator(ensure_csrf_cookie)
    def get(self, request, slot_id: int):
        if request.user.role != User.Role.PATIENT:
            return HttpResponseForbidden("Only patients can book appointments.")

        patient = request.user.patient_profile
        slot = get_object_or_404(
            AvailabilitySlot.objects.select_related("practitioner__user"),
            pk=slot_id,
        )

        appointment = (
            Appointment.objects.filter(patient=patient, slot=slot)
            .exclude(status=Appointment.Status.CANCELLED)
            .first()
        )
        if appointment is None:
            try:
                appointment = create_appointment(patient=patient, slot_id=slot.id)
            except DRFValidationError as exc:
                detail = exc.detail
                if isinstance(detail, dict):
                    detail = next(iter(detail.values()))
                messages.error(request, str(detail))
                return redirect("practitioner_detail", pk=slot.practitioner_id)

        if appointment.status != Appointment.Status.PENDING_PAYMENT:
            messages.info(request, "This booking is no longer awaiting payment.")
            return redirect("my_appointments")

        return render(
            request,
            self.template_name,
            {
                "appointment": appointment,
                "slot": appointment.slot,
                "practitioner": appointment.practitioner,
                "stripe_publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
            },
        )


class MyAppointmentsView(ProfileCompleteRequiredMixin, View):
    template_name = "web/my_appointments.html"

    def get(self, request):
        if request.user.role != User.Role.PATIENT:
            return HttpResponseForbidden("Patients only.")
        appointments = (
            Appointment.objects.filter(patient=request.user.patient_profile)
            .select_related("practitioner__user", "slot")
            .order_by("-created_at")
        )
        return render(request, self.template_name, {"appointments": appointments})

    def post(self, request):
        if request.user.role != User.Role.PATIENT:
            return HttpResponseForbidden("Patients only.")
        appointment_id = request.POST.get("appointment_id")
        appointment = get_object_or_404(
            Appointment, pk=appointment_id, patient=request.user.patient_profile
        )
        try:
            cancel_appointment(appointment=appointment, acting_user=request.user)
            messages.success(request, "Appointment cancelled.")
        except Exception as exc:
            messages.error(request, str(getattr(exc, "detail", exc)))
        return redirect("my_appointments")


class MyScheduleView(ProfileCompleteRequiredMixin, View):
    """Practitioner schedule + manual availability (FR-6, Docs/10)."""

    template_name = "web/my_schedule.html"

    def _context(self, request, form=None):
        profile = request.user.practitioner_profile
        return {
            "form": form or AvailabilitySlotForm(),
            "open_slots": AvailabilitySlot.objects.filter(
                practitioner=profile, is_booked=False
            ).order_by("start_time"),
            "appointments": (
                Appointment.objects.filter(practitioner=profile)
                .select_related("patient__user", "slot")
                .order_by("slot__start_time")
            ),
        }

    def get(self, request):
        if request.user.role != User.Role.PRACTITIONER:
            return HttpResponseForbidden("Practitioners only.")
        return render(request, self.template_name, self._context(request))

    def post(self, request):
        if request.user.role != User.Role.PRACTITIONER:
            return HttpResponseForbidden("Practitioners only.")

        profile = request.user.practitioner_profile
        action = request.POST.get("action", "create")

        if action == "delete":
            slot = get_object_or_404(
                AvailabilitySlot, pk=request.POST.get("slot_id"), practitioner=profile
            )
            try:
                delete_availability_slot(slot=slot, practitioner=profile)
                messages.success(request, "Availability slot removed.")
            except Exception as exc:
                messages.error(request, str(getattr(exc, "detail", exc)))
            return redirect("my_schedule")

        form = AvailabilitySlotForm(request.POST)
        if form.is_valid():
            try:
                create_availability_slot(
                    practitioner=profile,
                    start_time=form.cleaned_data["start_time"],
                    end_time=form.cleaned_data["end_time"],
                )
                messages.success(request, "Availability slot added.")
                return redirect("my_schedule")
            except DRFValidationError as exc:
                detail = exc.detail
                if isinstance(detail, dict):
                    for field, errs in detail.items():
                        msg = errs[0] if isinstance(errs, list) else errs
                        if field in form.fields:
                            form.add_error(field, str(msg))
                        else:
                            form.add_error(None, str(msg))
                else:
                    form.add_error(None, str(detail))

        return render(request, self.template_name, self._context(request, form=form))


class StaffDashboardView(StaffRequiredMixin, TemplateView):
    """Simple staff panel: analytics + users + appointments + payments."""

    template_name = "web/staff_dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        appointment_counts = {
            row["status"]: row["c"]
            for row in Appointment.objects.values("status").annotate(c=Count("id"))
        }
        payment_counts = {
            row["status"]: row["c"]
            for row in Payment.objects.values("status").annotate(c=Count("id"))
        }
        revenue = (
            Payment.objects.filter(status=Payment.Status.SUCCEEDED).aggregate(
                total=Sum("amount")
            )["total"]
            or 0
        )

        ctx["analytics"] = {
            "users_total": User.objects.count(),
            "patients": User.objects.filter(role=User.Role.PATIENT).count(),
            "practitioners": User.objects.filter(role=User.Role.PRACTITIONER).count(),
            "appointments_total": Appointment.objects.count(),
            "appointments_confirmed": appointment_counts.get(
                Appointment.Status.CONFIRMED, 0
            ),
            "appointments_pending": appointment_counts.get(
                Appointment.Status.PENDING_PAYMENT, 0
            ),
            "appointments_cancelled": appointment_counts.get(
                Appointment.Status.CANCELLED, 0
            ),
            "payments_succeeded": payment_counts.get(Payment.Status.SUCCEEDED, 0),
            "payments_pending": payment_counts.get(Payment.Status.PENDING, 0),
            "payments_refunded": payment_counts.get(Payment.Status.REFUNDED, 0),
            "revenue": revenue,
            "open_slots": AvailabilitySlot.objects.filter(is_booked=False).count(),
        }
        ctx["users"] = User.objects.order_by("-date_joined")[:100]
        ctx["appointments"] = (
            Appointment.objects.select_related(
                "patient__user", "practitioner__user", "slot"
            ).order_by("-created_at")[:100]
        )
        ctx["payments"] = (
            Payment.objects.select_related(
                "appointment__patient__user",
                "appointment__practitioner__user",
            ).order_by("-created_at")[:100]
        )
        return ctx
