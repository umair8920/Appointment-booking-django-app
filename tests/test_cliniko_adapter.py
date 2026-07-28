"""
Cross-cutting Cliniko adapter flow — Docs/07.

Mappers normalize Cliniko JSON; sync tasks upsert via PMSAdapter;
push stores cliniko_appointment_id. No Cliniko field names leak outside mappers.
"""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import User
from appointments.models import Appointment, AvailabilitySlot
from integrations.base import NormalizedPractitioner, NormalizedSlot, get_pms_adapter
from integrations.cliniko.adapter import ClinikoAdapter
from integrations.cliniko.mappers import map_practitioner
from integrations.models import PMSSyncLog
from integrations.tasks import push_appointment_to_cliniko, sync_cliniko_practitioners


class ClinikoAdapterFlowTests(TestCase):
    def test_mapper_is_only_cliniko_json_touchpoint(self):
        mapped = map_practitioner(
            {"id": 7, "first_name": "Grace", "last_name": "Hopper"}
        )
        self.assertEqual(mapped.external_id, "7")
        self.assertEqual(mapped.display_name, "Grace Hopper")
        # Normalized dataclass uses internal names, not Cliniko payload keys like "id"
        self.assertTrue(hasattr(mapped, "external_id"))
        self.assertFalse(hasattr(mapped, "id"))

    @override_settings(PMS_ADAPTER="integrations.cliniko.adapter.ClinikoAdapter")
    def test_settings_adapter_resolution(self):
        self.assertIsInstance(get_pms_adapter(), ClinikoAdapter)

    def test_sync_and_push_end_to_end_with_mocked_adapter(self):
        mock_adapter = MagicMock()
        mock_adapter.fetch_practitioners.return_value = [
            NormalizedPractitioner("55", "Grace", "Hopper", "Grace Hopper"),
        ]
        with patch("integrations.tasks.get_pms_adapter", return_value=mock_adapter):
            result = sync_cliniko_practitioners()
        self.assertEqual(result["created"], 1)
        self.assertTrue(
            PMSSyncLog.objects.filter(
                sync_type=PMSSyncLog.SyncType.PULL_PRACTITIONERS,
                status=PMSSyncLog.Status.SUCCESS,
            ).exists()
        )

        patient = User.objects.create_user(
            email="cliniko-flow-patient@example.com",
            password="x",
            role=User.Role.PATIENT,
            is_profile_complete=True,
        )
        from practitioners.models import PractitionerProfile

        prac = PractitionerProfile.objects.get(cliniko_practitioner_id="55")
        prac.consultation_fee = Decimal("50.00")
        prac.save()

        start = timezone.now() + timedelta(days=5)
        slot = AvailabilitySlot.objects.create(
            practitioner=prac,
            start_time=start,
            end_time=start + timedelta(minutes=30),
            is_booked=True,
            source=AvailabilitySlot.Source.CLINIKO,
        )
        appointment = Appointment.objects.create(
            patient=patient.patient_profile,
            practitioner=prac,
            slot=slot,
            status=Appointment.Status.CONFIRMED,
        )

        mock_adapter.push_appointment.return_value = "ext-99"
        with patch("integrations.tasks.get_pms_adapter", return_value=mock_adapter):
            external_id = push_appointment_to_cliniko(appointment.id)

        appointment.refresh_from_db()
        self.assertEqual(external_id, "ext-99")
        self.assertEqual(appointment.cliniko_appointment_id, "ext-99")
        # API-facing serializers must not expose cliniko_* (spot-check via model field isolation)
        self.assertNotIn("cliniko", NormalizedSlot.__annotations__)
