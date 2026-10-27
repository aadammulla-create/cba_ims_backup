from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.inventory.models import AssetCategory, EquipmentType, Brand, Asset
from apps.organizations.models import Department, Location
from apps.student_reservations.models import StudentReservation

User = get_user_model()


class StaffReturnWorkflowIntegrationTests(TestCase):
    """
    Focused regression tests for Phase 4E1: Repair Staff Return Workflow Integration.
    Tests real authenticated Django views through HTTP POST (no isolated service mocks or aliases).

    Scenarios covered:
    1. Admin successfully returns RELEASED equipment to the office with GOOD condition.
    2. Reservation transitions to RETURNED.
    3. Physical asset transitions back to AVAILABLE.
    4. School ID custody is cleared when its return is confirmed.
    5. Return audit event is recorded in AuditLog.
    6. Admin successfully records a valid guard handover.
    7. Guard handover transitions to RETURNED_TO_GUARD.
    8. The asset remains BORROWED and unavailable pending CBA inspection.
    9. School ID remains deposited during the guard handover.
    10. Unauthorized Faculty users cannot perform either operation (HTTP 403).
    11. Duplicate or invalid return attempts are rejected.
    12. Office return-condition options match official Asset.Condition choices (no EXCELLENT / DAMAGED).
    13. UNSERVICEABLE office return marks the physical asset DAMAGED.
    """

    def setUp(self):
        self.client = Client()

        # Users
        self.admin_user = User.objects.create_user(
            username='custodian_admin',
            email='custodian@cba.edu',
            password='Password123!',
            role='ADMIN',
            is_staff=True
        )
        self.faculty_user = User.objects.create_user(
            username='faculty_member',
            email='faculty@cba.edu',
            password='Password123!',
            role='FACULTY'
        )

        # Department & Location
        self.dept = Department.objects.create(code='CBA', name='College of Business Administration')
        self.loc = Location.objects.create(name='Property Office', department=self.dept)

        # Category, Brand, Equipment Type
        self.cat_proj = AssetCategory.objects.create(
            name='Projectors',
            code='PRJ',
            is_reservable=True
        )
        self.brand = Brand.objects.create(name='Epson')
        self.eq_type = EquipmentType.objects.create(
            category=self.cat_proj,
            name='Classroom LCD Projector',
            is_active=True
        )

    def _create_asset(self, code='PRJ-TEST-001', status=Asset.Status.AVAILABLE, condition=Asset.Condition.GOOD):
        return Asset.objects.create(
            asset_code=code,
            item_name='Epson EB-X06 Projector',
            category=self.cat_proj,
            equipment_type=self.eq_type,
            brand=self.brand,
            department=self.dept,
            current_location=self.loc,
            status=status,
            condition=condition,
            is_reservable=True
        )

    def _create_released_reservation(self, asset=None, student_name='Alex Rivera'):
        if not asset:
            asset = self._create_asset(code=f'PRJ-TEST-{StudentReservation.objects.count() + 1:03d}')

        now = timezone.now()
        res = StudentReservation.objects.create(
            student_id='202410888',
            student_name=student_name,
            course_year_section='BSBA 3-A',
            email='alex.rivera@cba.edu',
            contact_number='09171234567',
            category=self.cat_proj,
            equipment_type_ref=self.eq_type,
            equipment_type='Classroom LCD Projector',
            requested_pickup=now - timedelta(hours=2),
            requested_return=now + timedelta(hours=2),
            purpose='Strategic Management Capstone Defense',
            room_venue='CBA Room 3',
            status=StudentReservation.Status.RELEASED,
            asset=asset,
            released_by=self.admin_user,
            released_at=now - timedelta(hours=2),
            condition_at_release=Asset.Condition.GOOD,
            id_deposit_verified=True,
            id_deposited_at=now - timedelta(hours=2),
            id_collected_at=None,
        )

        asset.status = Asset.Status.BORROWED
        asset.save()
        return res, asset

    def test_01_to_05_admin_office_return_good_condition_lifecycle(self):
        """
        Scenarios 1-5:
        1. Admin successfully returns RELEASED equipment to office with GOOD condition.
        2. Reservation transitions to RETURNED.
        3. Physical asset transitions back to AVAILABLE.
        4. School ID custody is cleared when return is confirmed.
        5. Return audit event is recorded in AuditLog.
        """
        self.client.force_login(self.admin_user)
        res, asset = self._create_released_reservation()
        url = reverse('student_reservations:custodian_detail', kwargs={'pk': res.pk})

        post_data = {
            'action': 'return_office',
            'condition_at_return': Asset.Condition.GOOD,
            'id_collected_now': 'true',
            'return_remarks': 'Returned complete, tested operational, School ID returned.'
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, url)

        res.refresh_from_db()
        asset.refresh_from_db()

        # Scenario 2: Reservation transitions to RETURNED
        self.assertEqual(res.status, StudentReservation.Status.RETURNED)
        self.assertEqual(res.condition_at_return, Asset.Condition.GOOD)
        self.assertEqual(res.returned_to, self.admin_user)
        self.assertIsNotNone(res.returned_at)
        self.assertIn('Returned complete', res.return_remarks)

        # Scenario 3: Physical asset transitions back to AVAILABLE
        self.assertEqual(asset.status, Asset.Status.AVAILABLE)
        self.assertEqual(asset.condition, Asset.Condition.GOOD)

        # Scenario 4: School ID custody is cleared
        self.assertTrue(res.id_deposit_verified)
        self.assertIsNotNone(res.id_collected_at)
        self.assertEqual(res.id_returned_by, self.admin_user)

        # Scenario 5: Return audit event recorded
        audit_entry = AuditLog.objects.filter(
            action='STUDENT_RESERVATION_RETURNED',
            object_id=str(res.pk)
        ).first()
        self.assertIsNotNone(audit_entry)
        self.assertEqual(audit_entry.user, self.admin_user)
        self.assertEqual(audit_entry.changes.get('asset_code'), asset.asset_code)
        self.assertEqual(audit_entry.changes.get('resulting_asset_status'), Asset.Status.AVAILABLE)

    def test_06_to_09_admin_guard_handover_lifecycle(self):
        """
        Scenarios 6-9:
        6. Admin successfully records a valid guard handover.
        7. Guard handover transitions reservation to RETURNED_TO_GUARD.
        8. The asset remains BORROWED and unavailable pending CBA inspection.
        9. School ID remains deposited during guard handover.
        """
        self.client.force_login(self.admin_user)
        res, asset = self._create_released_reservation()
        url = reverse('student_reservations:custodian_detail', kwargs={'pk': res.pk})

        # Format using timezone.localtime() matching browser datetime-local input
        local_now = timezone.localtime()
        guard_time = (local_now - timedelta(minutes=30)).strftime('%Y-%m-%dT%H:%M')
        post_data = {
            'action': 'return_guard',
            'guard_returned_at': guard_time,
            'guard_handover_details': 'Security Guard Santos - Main Gate Guardhouse Logbook #402',
            'remarks': 'Handed over by student after 7 PM building closing.'
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, url)

        res.refresh_from_db()
        asset.refresh_from_db()

        # Scenario 7: Reservation transitions to RETURNED_TO_GUARD
        self.assertEqual(res.status, StudentReservation.Status.RETURNED_TO_GUARD)
        self.assertIsNotNone(res.guard_returned_at)
        self.assertEqual(res.guard_recorded_by, self.admin_user)
        self.assertEqual(res.guard_handover_details, 'Security Guard Santos - Main Gate Guardhouse Logbook #402')
        self.assertIn('Guard return', res.remarks)

        # Scenario 8: Asset remains BORROWED (unavailable) pending inspection
        self.assertEqual(asset.status, Asset.Status.BORROWED)

        # Scenario 9: School ID remains deposited at Property Office
        self.assertTrue(res.id_deposit_verified)
        self.assertIsNone(res.id_collected_at)
        self.assertIsNone(res.id_returned_by)

    def test_10_unauthorized_faculty_cannot_perform_returns(self):
        """Scenario 10: Unauthorized Faculty users cannot perform office return or guard handover (HTTP 403)."""
        self.client.force_login(self.faculty_user)
        res, _ = self._create_released_reservation()
        url = reverse('student_reservations:custodian_detail', kwargs={'pk': res.pk})

        # Attempt office return
        resp_office = self.client.post(url, {
            'action': 'return_office',
            'condition_at_return': Asset.Condition.GOOD,
            'id_collected_now': 'true'
        })
        self.assertEqual(resp_office.status_code, 403)

        # Attempt guard return
        local_now = timezone.localtime()
        guard_time = (local_now - timedelta(minutes=15)).strftime('%Y-%m-%dT%H:%M')
        resp_guard = self.client.post(url, {
            'action': 'return_guard',
            'guard_returned_at': guard_time,
            'guard_handover_details': 'Guard Post'
        })
        self.assertEqual(resp_guard.status_code, 403)

        # Verify reservation status unchanged
        res.refresh_from_db()
        self.assertEqual(res.status, StudentReservation.Status.RELEASED)

    def test_11_duplicate_or_invalid_return_attempts_rejected(self):
        """Scenario 11: Duplicate or invalid return attempts are rejected with validation errors."""
        self.client.force_login(self.admin_user)
        res, asset = self._create_released_reservation()
        url = reverse('student_reservations:custodian_detail', kwargs={'pk': res.pk})

        # 1. Missing condition on office return
        resp_bad_cond = self.client.post(url, {
            'action': 'return_office',
            'condition_at_return': '',
            'id_collected_now': 'true'
        })
        self.assertEqual(resp_bad_cond.status_code, 200)
        self.assertContains(resp_bad_cond, 'Failed to record return: condition is required.')

        # 2. Missing guard handover details on guard return
        local_now = timezone.localtime()
        resp_bad_guard = self.client.post(url, {
            'action': 'return_guard',
            'guard_returned_at': (local_now - timedelta(minutes=10)).strftime('%Y-%m-%dT%H:%M'),
            'guard_handover_details': ''
        })
        self.assertEqual(resp_bad_guard.status_code, 200)
        self.assertContains(resp_bad_guard, 'Failed to record guard handover.')

        # 3. Successful office return first
        self.client.post(url, {
            'action': 'return_office',
            'condition_at_return': Asset.Condition.GOOD,
            'id_collected_now': 'true'
        })
        res.refresh_from_db()
        self.assertEqual(res.status, StudentReservation.Status.RETURNED)

        # 4. Duplicate return attempt on already RETURNED reservation
        resp_duplicate = self.client.post(url, {
            'action': 'return_office',
            'condition_at_return': Asset.Condition.GOOD,
            'id_collected_now': 'true'
        }, follow=True)
        self.assertEqual(resp_duplicate.status_code, 200)
        self.assertContains(resp_duplicate, 'Cannot process office return')
        res.refresh_from_db()
        self.assertEqual(res.status, StudentReservation.Status.RETURNED)

    def test_12_office_return_condition_dropdown_choices(self):
        """
        Scenario 12: Direct-office return-condition dropdown renders all official Asset.Condition choices
        and does NOT contain legacy hardcoded options ('EXCELLENT' or 'DAMAGED').
        """
        self.client.force_login(self.admin_user)
        res, _ = self._create_released_reservation()
        url = reverse('student_reservations:custodian_detail', kwargs={'pk': res.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Must contain all official Asset.Condition choices
        for cond_val, cond_label in Asset.Condition.choices:
            expected_option = f'value="{cond_val}"'
            self.assertContains(response, expected_option)

        # Must NOT contain hardcoded unsupported values
        self.assertNotContains(response, 'value="EXCELLENT"')
        self.assertNotContains(response, 'value="DAMAGED"')

    def test_13_unserviceable_office_return_marks_asset_damaged(self):
        """
        Scenario 13: UNSERVICEABLE office return transitions reservation to RETURNED,
        and marks the physical asset DAMAGED (not AVAILABLE).
        """
        self.client.force_login(self.admin_user)
        res, asset = self._create_released_reservation()
        url = reverse('student_reservations:custodian_detail', kwargs={'pk': res.pk})

        post_data = {
            'action': 'return_office',
            'condition_at_return': Asset.Condition.UNSERVICEABLE,
            'id_collected_now': 'true',
            'return_remarks': 'Projector bulb burst, casing cracked; unusable.'
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302)

        res.refresh_from_db()
        asset.refresh_from_db()

        self.assertEqual(res.status, StudentReservation.Status.RETURNED)
        self.assertEqual(res.condition_at_return, Asset.Condition.UNSERVICEABLE)

        # Crucial lifecycle rule: Asset is DAMAGED, not AVAILABLE
        self.assertEqual(asset.status, Asset.Status.DAMAGED)
        self.assertEqual(asset.condition, Asset.Condition.UNSERVICEABLE)
