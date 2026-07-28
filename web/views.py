"""
Demo UI views — call domain services/models directly (Docs/10).

No DRF HTTP from the server. Stripe Elements uses fetch() to /api/payments/...
"""

from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
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
from appointments.services import cancel_appointment, create_appointment
from practitioners.models import PractitionerProfile
from web.forms import CompleteProfileForm
from web.mixins import ProfileCompleteRequiredMixin


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
    template_name = "web/my_schedule.html"

    def get(self, request):
        if request.user.role != User.Role.PRACTITIONER:
            return HttpResponseForbidden("Practitioners only.")
        appointments = (
            Appointment.objects.filter(practitioner=request.user.practitioner_profile)
            .select_related("patient__user", "slot")
            .order_by("slot__start_time")
        )
        return render(request, self.template_name, {"appointments": appointments})
