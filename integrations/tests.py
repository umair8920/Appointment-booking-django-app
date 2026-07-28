"""Cliniko adapter / sync tests — Docs/07 (mocked HTTP, no live Cliniko)."""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import User
from appointments.models import Appointment, AvailabilitySlot
from integrations.base import NormalizedPractitioner, NormalizedSlot, get_pms_adapter
from integrations.cliniko.adapter import ClinikoAdapter
from integrations.cliniko.mappers import map_available_time, map_practitioner
from integrations.models import PMSSyncLog
from integrations.tasks import (
    push_appointment_to_cliniko,
    sync_cliniko_availability,
    sync_cliniko_practitioners,
)
from practitioners.models import PractitionerProfile


class MapperTests(TestCase):
    def test_map_practitioner(self):
        mapped = map_practitioner(
            {"id": 42, "first_name": "Ada", "last_name": "Lovelace"}
        )
        self.assertEqual(mapped.external_id, "42")
        self.assertEqual(mapped.display_name, "Ada Lovelace")

    def test_map_available_time(self):
        mapped = map_available_time(
            {"appointment_start": "2026-08-01T09:00:00Z"},
            external_practitioner_id="42",
            duration_minutes=30,
        )
        self.assertIsNotNone(mapped)
        assert mapped is not None
        self.assertEqual(mapped.external_practitioner_id, "42")
        self.assertEqual(
            mapped.end_time - mapped.start_time, timedelta(minutes=30)
        )


@override_settings(
    PMS_ADAPTER="integrations.cliniko.adapter.ClinikoAdapter",
    CLINIKO_API_KEY="test-key",
    CLINIKO_BUSINESS_ID="1",
    CLINIKO_APPOINTMENT_TYPE_ID="9",
)
class AdapterAndTaskTests(TestCase):
    def test_get_pms_adapter_resolves_settings(self):
        adapter = get_pms_adapter()
        self.assertIsInstance(adapter, ClinikoAdapter)

    def test_sync_practitioners_upserts(self):
        mock_adapter = MagicMock()
        mock_adapter.fetch_practitioners.return_value = [
            NormalizedPractitioner("100", "Ada", "Lovelace", "Ada Lovelace"),
        ]
        with patch("integrations.tasks.get_pms_adapter", return_value=mock_adapter):
            result = sync_cliniko_practitioners()

        self.assertEqual(result["created"], 1)
        profile = PractitionerProfile.objects.get(cliniko_practitioner_id="100")
        self.assertEqual(profile.specialization, "Ada Lovelace")
        self.assertTrue(profile.user.is_profile_complete)
        self.assertEqual(
            PMSSyncLog.objects.filter(
                sync_type=PMSSyncLog.SyncType.PULL_PRACTITIONERS,
                status=PMSSyncLog.Status.SUCCESS,
            ).count(),
            1,
        )

        # Second sync is update, not duplicate
        with patch("integrations.tasks.get_pms_adapter", return_value=mock_adapter):
            result2 = sync_cliniko_practitioners()
        self.assertEqual(result2["created"], 0)
        self.assertEqual(result2["updated"], 1)
        self.assertEqual(
            PractitionerProfile.objects.filter(cliniko_practitioner_id="100").count(),
            1,
        )

    def test_sync_availability_creates_cliniko_slots(self):
        user = User.objects.create_user(
            email="doc-sync@example.com",
            password="x",
            role=User.Role.PRACTITIONER,
            is_profile_complete=True,
        )
        profile = user.practitioner_profile
        profile.cliniko_practitioner_id = "100"
        profile.consultation_fee = Decimal("40.00")
        profile.save()

        start = timezone.now() + timedelta(days=1)
        mock_adapter = MagicMock()
        mock_adapter.fetch_availability.return_value = [
            NormalizedSlot("100", start, start + timedelta(minutes=30)),
        ]
        with patch("integrations.tasks.get_pms_adapter", return_value=mock_adapter):
            sync_cliniko_availability()

        slot = AvailabilitySlot.objects.get(practitioner=profile, start_time=start)
        self.assertEqual(slot.source, AvailabilitySlot.Source.CLINIKO)
        self.assertFalse(slot.is_booked)

    def test_push_appointment_stores_external_id(self):
        patient_user = User.objects.create_user(
            email="patient-sync@example.com",
            password="x",
            role=User.Role.PATIENT,
            is_profile_complete=True,
        )
        prac_user = User.objects.create_user(
            email="prac-sync@example.com",
            password="x",
            role=User.Role.PRACTITIONER,
            is_profile_complete=True,
        )
        prac = prac_user.practitioner_profile
        prac.cliniko_practitioner_id = "100"
        prac.save()
        start = timezone.now() + timedelta(days=2)
        slot = AvailabilitySlot.objects.create(
            practitioner=prac,
            start_time=start,
            end_time=start + timedelta(minutes=30),
            is_booked=True,
        )
        appointment = Appointment.objects.create(
            patient=patient_user.patient_profile,
            practitioner=prac,
            slot=slot,
            status=Appointment.Status.CONFIRMED,
        )

        mock_adapter = MagicMock()
        mock_adapter.push_appointment.return_value = "cliniko-appt-9"
        with patch("integrations.tasks.get_pms_adapter", return_value=mock_adapter):
            external_id = push_appointment_to_cliniko(appointment.id)

        appointment.refresh_from_db()
        self.assertEqual(external_id, "cliniko-appt-9")
        self.assertEqual(appointment.cliniko_appointment_id, "cliniko-appt-9")

    def test_adapter_fetch_availability_uses_client(self):
        client = MagicMock()
        client.list_all.return_value = [
            {"appointment_start": "2026-08-01T10:00:00Z"},
        ]
        client.get.return_value = {"duration_in_minutes": 45}
        adapter = ClinikoAdapter(client=client)
        slots = adapter.fetch_availability("100")
        self.assertEqual(len(slots), 1)
        self.assertEqual(slots[0].end_time - slots[0].start_time, timedelta(minutes=45))
        client.list_all.assert_called()
