from decimal import Decimal
from datetime import timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError, PermissionDenied

from apps.accounts.models import User
from apps.organizations.models import Department, Location, Employee
from apps.inventory.models import Asset, AssetCategory, Brand
from apps.inventory.forms import AssetUpdateForm
from apps.student_reservations.models import StudentReservation
from apps.student_reservations import services as sr_services
from apps.student_reservations.security import mask_contact_info
from apps.disposals.models import AssetDisposal
from apps.disposals import services as disposal_services


class Phase3AWorkflowIntegrityTests(TestCase):
    """
    Test suite verifying the 11 Phase 3A requirements:
    1. Disposal blocked by approved student reservation.
    2. Disposal blocked by released student equipment.
    3. Disposal blocked by guard-return awaiting inspection.
    4. Disposal permitted after resolved historical reservations.
    5. Forged AssetUpdateView POST cannot alter workflow-managed fields.
    6. Normal metadata edits remain possible.
    7. Asset registration still functions.
    8. Asset details accurately represent student reservation context and mask student PII.
    9. Existing date-based borrowing/approval conflict protection is preserved.
    10. Asset deletion with reservation history returns a graceful response.
    11. Existing role-based authorization is preserved.
    """

    def setUp(self):
        self.client = Client()

        # Users
        self.admin = User.objects.create_user(
            username='admin_integrity',
            email='admin@cba.edu',
            password='Password123!',
            role=User.Role.ADMIN
        )
        self.dean = User.objects.create_user(
            username='dean_integrity',
            email='dean@cba.edu',
            password='Password123!',
            role=User.Role.DEAN
        )
        self.chair = User.objects.create_user(
            username='chair_integrity',
            email='chair@cba.edu',
            password='Password123!',
            role=User.Role.DEPT_CHAIR
        )
        self.faculty = User.objects.create_user(
            username='faculty_integrity',
            email='faculty@cba.edu',
            password='Password123!',
            role=User.Role.FACULTY
        )

        # Organization
        self.dept_it = Department.objects.create(name='Information Technology', code='IT')
        self.dept_ba = Department.objects.create(name='Business Administration', code='BA')
        self.loc_it = Location.objects.create(name='IT Lab 1', building='IT Wing', room_number='IT-101', department=self.dept_it)
        self.loc_ba = Location.objects.create(name='BA Dean Office', building='CBA Main', room_number='BA-201', department=self.dept_ba)

        self.emp_chair = Employee.objects.create(
            user=self.chair,
            employee_id='EMP-CH-01',
            first_name='Maria',
            last_name='Chair',
            department=self.dept_it,
            location=self.loc_it
        )

        # Inventory fixtures
        self.cat_it = AssetCategory.objects.create(
            name='IT Equipment',
            code='ITE',
            is_active=True,
            is_reservable=True
        )
        self.brand_dell = Brand.objects.create(name='Dell', is_active=True)

        self.asset = Asset.objects.create(
            item_name='Dell Latitude 5420',
            category=self.cat_it,
            brand=self.brand_dell,
            model='5420',
            serial_number='SN-DELL-12345',
            property_number='NORSU-CBA-2026-0099',
            department=self.dept_it,
            current_location=self.loc_it,
            condition=Asset.Condition.GOOD,
            status=Asset.Status.AVAILABLE,
            acquisition_cost=Decimal('45000.00'),
            created_by=self.admin
        )

        self.now = timezone.now()

    def _create_reservation(self, asset=None, status=StudentReservation.Status.APPROVED, **kwargs):
        """Helper to create student reservation fixture."""
        defaults = {
            'student_id': '2023-10042',
            'student_name': 'Juan Dela Cruz',
            'course_year_section': 'BSBA 3-A',
            'email': 'juan.delacruz@cba.edu',
            'contact_number': '09171234567',
            'category': self.cat_it,
            'equipment_type': 'Laptop',
            'asset': asset or self.asset,
            'requested_pickup': self.now + timedelta(hours=2),
            'requested_return': self.now + timedelta(hours=5),
            'purpose': 'Academic Presentation',
            'room_venue': 'CBA Hall 101',
            'status': status,
        }
        defaults.update(kwargs)
        return StudentReservation.objects.create(**defaults)

    # --------------------------------------------------------------------------
    # 1. Disposal blocked by approved student reservation
    # --------------------------------------------------------------------------
    def test_disposal_blocked_by_approved_student_reservation(self):
        self._create_reservation(status=StudentReservation.Status.APPROVED)

        is_eligible, reason = disposal_services.validate_disposal_eligibility(self.asset)
        self.assertFalse(is_eligible)
        self.assertIn("student reservation", reason.lower())

        is_comp_eligible, comp_reason = disposal_services.validate_completion_eligibility(self.asset)
        self.assertFalse(is_comp_eligible)
        self.assertIn("student reservation", comp_reason.lower())

        with self.assertRaises(ValidationError):
            disposal_services.request_disposal(
                asset=self.asset,
                requested_by=self.admin,
                reason="Damaged beyond economical repair"
            )

    # --------------------------------------------------------------------------
    # 2. Disposal blocked by released student equipment
    # --------------------------------------------------------------------------
    def test_disposal_blocked_by_released_student_equipment(self):
        self._create_reservation(
            status=StudentReservation.Status.RELEASED,
            released_at=self.now - timedelta(hours=1)
        )

        is_eligible, reason = disposal_services.validate_disposal_eligibility(self.asset)
        self.assertFalse(is_eligible)
        self.assertIn("student reservation", reason.lower())

        is_comp_eligible, comp_reason = disposal_services.validate_completion_eligibility(self.asset)
        self.assertFalse(is_comp_eligible)
        self.assertIn("student reservation", comp_reason.lower())

        with self.assertRaises(ValidationError):
            disposal_services.request_disposal(
                asset=self.asset,
                requested_by=self.admin,
                reason="Disposal attempt during active loan"
            )

    # --------------------------------------------------------------------------
    # 3. Disposal blocked by guard-return awaiting inspection
    # --------------------------------------------------------------------------
    def test_disposal_blocked_by_guard_return_awaiting_inspection(self):
        self._create_reservation(
            status=StudentReservation.Status.RETURNED_TO_GUARD,
            returned_at=self.now - timedelta(minutes=30),
            guard_returned_at=self.now - timedelta(minutes=30)
        )

        is_eligible, reason = disposal_services.validate_disposal_eligibility(self.asset)
        self.assertFalse(is_eligible)
        self.assertIn("student reservation", reason.lower())

        is_comp_eligible, comp_reason = disposal_services.validate_completion_eligibility(self.asset)
        self.assertFalse(is_comp_eligible)
        self.assertIn("student reservation", comp_reason.lower())

        with self.assertRaises(ValidationError):
            disposal_services.request_disposal(
                asset=self.asset,
                requested_by=self.admin,
                reason="Disposal attempt while held at guard post"
            )

    # --------------------------------------------------------------------------
    # 4. Disposal permitted after resolved historical reservations
    # --------------------------------------------------------------------------
    def test_disposal_permitted_after_resolved_historical_reservations(self):
        # Create completed, cancelled, rejected, and no-show history
        self._create_reservation(status=StudentReservation.Status.RETURNED, student_id='2023-11111')
        self._create_reservation(status=StudentReservation.Status.REJECTED, student_id='2023-22222')
        self._create_reservation(status=StudentReservation.Status.CANCELLED, student_id='2023-33333')
        self._create_reservation(status=StudentReservation.Status.NO_SHOW, student_id='2023-44444')
        # PENDING reservations do not hold inventory and should not prohibit disposal
        self._create_reservation(status=StudentReservation.Status.PENDING, student_id='2023-55555')

        is_eligible, reason = disposal_services.validate_disposal_eligibility(self.asset)
        self.assertTrue(is_eligible, f"Expected eligible, got: {reason}")

        is_comp_eligible, comp_reason = disposal_services.validate_completion_eligibility(self.asset)
        self.assertTrue(is_comp_eligible, f"Expected comp eligible, got: {comp_reason}")

        # Request disposal successfully
        disposal = disposal_services.request_disposal(
            asset=self.asset,
            requested_by=self.admin,
            reason="Unserviceable motherboard failure"
        )
        self.assertEqual(disposal.status, AssetDisposal.Status.PENDING)

    # --------------------------------------------------------------------------
    # 5. Forged AssetUpdateView POST cannot alter workflow-managed fields
    # --------------------------------------------------------------------------
    def test_forged_asset_update_post_cannot_alter_workflow_fields(self):
        self.client.login(username='admin_integrity', password='Password123!')
        url = reverse('inventory:asset_edit', kwargs={'asset_code': self.asset.asset_code})

        original_status = self.asset.status
        original_dept_pk = self.asset.department.pk
        original_loc_pk = self.asset.current_location.pk

        # Forged POST attempting to force DISPOSED status, different department, and location
        forged_data = {
            'item_name': 'Tampered Asset Name',
            'category': self.cat_it.pk,
            'brand': self.brand_dell.pk,
            'model': '5420',
            'property_number': self.asset.property_number,
            'serial_number': self.asset.serial_number,
            'acquisition_cost': '45000.00',
            'condition': Asset.Condition.POOR,
            'remarks': 'Attempting illegal bypass',
            # Forged workflow fields:
            'status': Asset.Status.DISPOSED,
            'department': self.dept_ba.pk,
            'current_location': self.loc_ba.pk,
        }

        response = self.client.post(url, forged_data)
        self.assertEqual(response.status_code, 302)

        self.asset.refresh_from_db()
        # Item name and remarks can be updated
        self.assertEqual(self.asset.item_name, 'Tampered Asset Name')
        # Workflow-managed fields must remain unchanged
        self.assertEqual(self.asset.status, original_status)
        self.assertEqual(self.asset.department.pk, original_dept_pk)
        self.assertEqual(self.asset.current_location.pk, original_loc_pk)
        self.assertEqual(self.asset.condition, Asset.Condition.GOOD)

    # --------------------------------------------------------------------------
    # 6. Normal metadata edits remain possible
    # --------------------------------------------------------------------------
    def test_normal_metadata_edits_remain_possible(self):
        self.client.login(username='admin_integrity', password='Password123!')
        url = reverse('inventory:asset_edit', kwargs={'asset_code': self.asset.asset_code})

        post_data = {
            'item_name': 'Dell Latitude 5420 (Updated Metadata)',
            'category': self.cat_it.pk,
            'brand': self.brand_dell.pk,
            'model': '5420-Gen2',
            'property_number': self.asset.property_number,
            'serial_number': 'SN-DELL-NEW99',
            'acquisition_cost': '48000.00',
            'remarks': 'Updated operational notes and description.',
        }

        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302)

        self.asset.refresh_from_db()
        self.assertEqual(self.asset.item_name, 'Dell Latitude 5420 (Updated Metadata)')
        self.assertEqual(self.asset.model, '5420-Gen2')
        self.assertEqual(self.asset.serial_number, 'SN-DELL-NEW99')
        self.assertEqual(self.asset.acquisition_cost, Decimal('48000.00'))
        self.assertEqual(self.asset.condition, Asset.Condition.GOOD)
        self.assertEqual(self.asset.remarks, 'Updated operational notes and description.')

    # --------------------------------------------------------------------------
    # 7. Asset registration still functions
    # --------------------------------------------------------------------------
    def test_asset_registration_still_functions(self):
        self.client.login(username='admin_integrity', password='Password123!')
        create_url = reverse('inventory:asset_create')

        post_data = {
            'item_name': 'Epson EB-X51 Projector',
            'category': self.cat_it.pk,
            'brand': self.brand_dell.pk,
            'model': 'EB-X51',
            'description': '3800 Lumens XGA Projector',
            'property_number': 'NORSU-NEW-2026-999',
            'serial_number': 'SN-PROJ-999',
            'department': self.dept_it.pk,
            'current_location': self.loc_it.pk,
            'acquisition_date': '2026-03-01',
            'acquisition_cost': '28500.00',
            'supplier': 'Epson Philippines',
            'condition': Asset.Condition.NEW,
            'status': Asset.Status.AVAILABLE,
            'remarks': 'New inventory item.',
        }

        response = self.client.post(create_url, post_data)
        self.assertEqual(response.status_code, 302)

        created = Asset.objects.get(property_number='NORSU-NEW-2026-999')
        self.assertTrue(created.asset_code.startswith('CBA-ITE-'))
        self.assertEqual(created.status, Asset.Status.AVAILABLE)
        self.assertEqual(created.department, self.dept_it)
        self.assertEqual(created.current_location, self.loc_it)

    # --------------------------------------------------------------------------
    # 8. Asset details accurately represent student reservation context and mask student PII
    # --------------------------------------------------------------------------
    def test_asset_details_accurately_represent_student_reservation_context(self):
        # Scenario 8a: Released active student loan
        loan = self._create_reservation(
            status=StudentReservation.Status.RELEASED,
            released_at=self.now - timedelta(hours=1)
        )
        self.asset.status = Asset.Status.AVAILABLE
        self.asset.save()

        # Admin view - unmasked PII
        self.client.login(username='admin_integrity', password='Password123!')
        detail_url = reverse('inventory:asset_detail', kwargs={'asset_code': self.asset.asset_code})
        res_admin = self.client.get(detail_url)
        self.assertEqual(res_admin.status_code, 200)
        self.assertEqual(res_admin.context['current_student_loan'], loan)
        self.assertFalse(res_admin.context['can_borrow'])  # Out on student loan!
        self.assertTrue(res_admin.context['can_view_student_pii'])
        self.assertContains(res_admin, loan.email)
        self.assertContains(res_admin, loan.contact_number)

        # Faculty view - masked PII
        # Assign asset temporarily to faculty to permit access to AssetDetailView
        from apps.assignments.models import AssetAssignment
        from apps.organizations.models import Employee
        emp_fac = Employee.objects.create(
            user=self.faculty,
            employee_id='EMP-FAC-99',
            first_name='Faculty',
            last_name='User',
            department=self.dept_it,
            location=self.loc_it
        )
        AssetAssignment.objects.create(
            asset=self.asset,
            employee=emp_fac,
            assigned_by=self.admin,
            status='ACTIVE'
        )

        self.client.login(username='faculty_integrity', password='Password123!')
        res_fac = self.client.get(detail_url)
        self.assertEqual(res_fac.status_code, 200)
        self.assertFalse(res_fac.context['can_view_student_pii'])

        masked_email, masked_phone = mask_contact_info(loan.email, loan.contact_number)
        self.assertContains(res_fac, masked_email)
        self.assertNotContains(res_fac, loan.email)

    # --------------------------------------------------------------------------
    # 9. Existing date-based borrowing/approval conflict protection is preserved
    # --------------------------------------------------------------------------
    def test_existing_date_based_borrowing_conflict_protection_preserved(self):
        # Create approved future reservation for 2:00 PM to 5:00 PM tomorrow
        pickup = self.now + timedelta(days=1, hours=2)
        return_time = self.now + timedelta(days=1, hours=5)
        self._create_reservation(
            status=StudentReservation.Status.APPROVED,
            requested_pickup=pickup,
            requested_return=return_time
        )

        # Overlapping period should fail availability check
        is_avail, reason = sr_services.check_asset_availability(
            asset=self.asset,
            requested_pickup=pickup + timedelta(minutes=30),
            requested_return=return_time + timedelta(hours=1)
        )
        self.assertFalse(is_avail)
        self.assertIn("overlapping approved student reservation", reason.lower())

        # Non-overlapping period (earlier in the day) should be available
        is_avail_non_overlap, reason_ok = sr_services.check_asset_availability(
            asset=self.asset,
            requested_pickup=pickup - timedelta(hours=3),
            requested_return=pickup - timedelta(minutes=30)
        )
        self.assertTrue(is_avail_non_overlap, f"Expected non-overlapping to be available, got: {reason_ok}")

    # --------------------------------------------------------------------------
    # 10. Asset deletion with reservation history returns a graceful response
    # --------------------------------------------------------------------------
    def test_asset_deletion_with_reservation_history_graceful_response(self):
        self._create_reservation(status=StudentReservation.Status.RETURNED)
        self.client.login(username='admin_integrity', password='Password123!')
        delete_url = reverse('inventory:asset_delete', kwargs={'asset_code': self.asset.asset_code})

        # GET should redirect to detail with error message
        res_get = self.client.get(delete_url)
        self.assertEqual(res_get.status_code, 302)
        self.assertRedirects(res_get, reverse('inventory:asset_detail', kwargs={'asset_code': self.asset.asset_code}))

        # POST should redirect gracefully without ProtectedError HTTP 500
        res_post = self.client.post(delete_url)
        self.assertEqual(res_post.status_code, 302)
        self.assertRedirects(res_post, reverse('inventory:asset_detail', kwargs={'asset_code': self.asset.asset_code}))

        # Asset and reservation must still exist
        self.assertTrue(Asset.objects.filter(asset_code=self.asset.asset_code).exists())
        self.assertTrue(StudentReservation.objects.filter(asset=self.asset).exists())

    # --------------------------------------------------------------------------
    # 11. Existing role-based authorization is preserved
    # --------------------------------------------------------------------------
    def test_existing_role_based_authorization_is_preserved(self):
        edit_url = reverse('inventory:asset_edit', kwargs={'asset_code': self.asset.asset_code})
        delete_url = reverse('inventory:asset_delete', kwargs={'asset_code': self.asset.asset_code})

        # Faculty cannot access edit or delete
        self.client.login(username='faculty_integrity', password='Password123!')
        self.assertEqual(self.client.get(edit_url).status_code, 403)
        self.assertEqual(self.client.post(edit_url, {}).status_code, 403)
        self.assertEqual(self.client.get(delete_url).status_code, 403)
        self.assertEqual(self.client.post(delete_url, {}).status_code, 403)

        # Department Chair cannot access asset edit or delete (Admin only)
        self.client.login(username='chair_integrity', password='Password123!')
        self.assertEqual(self.client.get(edit_url).status_code, 403)
        self.assertEqual(self.client.get(delete_url).status_code, 403)

        # Non-admin cannot perform custodian reservation approval
        res = self._create_reservation(status=StudentReservation.Status.PENDING)
        with self.assertRaises(PermissionDenied):
            sr_services.approve_reservation(
                reservation=res,
                asset=self.asset,
                reviewed_by=self.faculty
            )

    # --------------------------------------------------------------------------
    # 12. Django Admin bypass is closed for existing assets (Task 1)
    # --------------------------------------------------------------------------
    def test_django_admin_bypass_closed_for_existing_assets(self):
        from django.contrib.admin.sites import AdminSite
        from apps.inventory.admin import AssetAdmin

        site = AdminSite()
        asset_admin = AssetAdmin(Asset, site)

        # Existing asset must have workflow fields marked readonly
        readonly_existing = asset_admin.get_readonly_fields(request=None, obj=self.asset)
        self.assertIn('status', readonly_existing)
        self.assertIn('department', readonly_existing)
        self.assertIn('current_location', readonly_existing)

        # New asset creation must allow initial department and location assignment
        readonly_new = asset_admin.get_readonly_fields(request=None, obj=None)
        self.assertNotIn('status', readonly_new)
        self.assertNotIn('department', readonly_new)
        self.assertNotIn('current_location', readonly_new)

        # Server-side save_model lock prevents tampering on existing asset change
        tampered_asset = Asset.objects.get(pk=self.asset.pk)
        tampered_asset.status = Asset.Status.DISPOSED
        tampered_asset.department = self.dept_ba
        tampered_asset.current_location = self.loc_ba

        # Trigger save_model with change=True
        asset_admin.save_model(request=None, obj=tampered_asset, form=None, change=True)

        reloaded = Asset.objects.get(pk=self.asset.pk)
        self.assertEqual(reloaded.status, Asset.Status.AVAILABLE)
        self.assertEqual(reloaded.department, self.dept_it)
        self.assertEqual(reloaded.current_location, self.loc_it)

    # --------------------------------------------------------------------------
    # 13. All StudentReservation status enums accurately represented (Task 2)
    # --------------------------------------------------------------------------
    def test_all_student_reservation_status_enums_accurately_represented(self):
        self.client.login(username='admin_integrity', password='Password123!')
        detail_url = reverse('inventory:asset_detail', kwargs={'asset_code': self.asset.asset_code})

        # 13a. Approved future reservation (awaiting pickup)
        future_res = self._create_reservation(
            status=StudentReservation.Status.APPROVED,
            requested_pickup=self.now + timedelta(days=1, hours=1),
            requested_return=self.now + timedelta(days=1, hours=4)
        )
        res = self.client.get(detail_url)
        self.assertEqual(res.status_code, 200)
        self.assertIn(future_res, res.context['upcoming_student_reservations'])
        self.assertTrue(res.context['can_borrow'])  # Future reservation does not block immediate borrowing

        # 13b. Physically released active loan
        active_res = self._create_reservation(
            status=StudentReservation.Status.RELEASED,
            released_at=self.now - timedelta(hours=1),
            requested_return=self.now + timedelta(hours=2)
        )
        res = self.client.get(detail_url)
        self.assertEqual(res.context['current_student_loan'], active_res)
        self.assertFalse(res.context['can_borrow'])  # Physically out, cannot borrow

        # 13c. Returned to security guard awaiting custodian inspection
        active_res.status = StudentReservation.Status.RETURNED_TO_GUARD
        active_res.guard_returned_at = self.now - timedelta(minutes=20)
        active_res.save()

        res = self.client.get(detail_url)
        self.assertEqual(res.context['guard_return_pending_inspection'], active_res)
        self.assertFalse(res.context['can_borrow'])  # Awaiting inspection at guard post
        self.assertContains(res, "Returned to Security Guard (Pending Inspection)")

        # 13d. Completed and historical statuses
        active_res.status = StudentReservation.Status.RETURNED
        active_res.returned_at = self.now
        active_res.save()

        rej_res = self._create_reservation(status=StudentReservation.Status.REJECTED)
        can_res = self._create_reservation(status=StudentReservation.Status.CANCELLED)
        noshow_res = self._create_reservation(status=StudentReservation.Status.NO_SHOW)

        res = self.client.get(detail_url)
        history = res.context['student_reservation_history']
        self.assertIn(active_res, history)
        self.assertIn(rej_res, history)
        self.assertIn(can_res, history)
        self.assertIn(noshow_res, history)

        # Confirm all badges render in history table
        self.assertContains(res, "Returned")
        self.assertContains(res, "Rejected")
        self.assertContains(res, "Cancelled")
        self.assertContains(res, "No Show")

    # --------------------------------------------------------------------------
    # 14. Cross-module date-range conflict handling (Task 3)
    # --------------------------------------------------------------------------
    def test_cross_module_future_reservation_date_overlap_conflict(self):
        from apps.borrowing import services as borrowing_services

        # Tomorrow 10:00 AM to 1:00 PM: Student reservation APPROVED
        pickup = self.now + timedelta(days=1, hours=2)
        return_time = self.now + timedelta(days=1, hours=5)
        self._create_reservation(
            status=StudentReservation.Status.APPROVED,
            requested_pickup=pickup,
            requested_return=return_time
        )

        # Faculty employee profile
        from apps.organizations.models import Employee
        emp_faculty = Employee.objects.create(
            user=self.faculty,
            employee_id='EMP-FAC-CROSS',
            first_name='Elena',
            last_name='Faculty',
            department=self.dept_it,
            location=self.loc_it
        )

        # Scenario 14a: Overlapping faculty borrowing request must be rejected
        overlap_start = pickup + timedelta(hours=1)
        overlap_return = return_time + timedelta(hours=2)
        with self.assertRaises(ValidationError) as ctx:
            borrowing_services.request_borrowing(
                asset=self.asset,
                borrower=emp_faculty,
                purpose="Classroom lecture",
                requested_start=overlap_start,
                requested_return=overlap_return,
                created_by=self.faculty
            )
        self.assertIn("already reserved for a student", str(ctx.exception).lower())

        # Scenario 14b: Legitimate non-overlapping faculty borrowing succeeds
        non_overlap_start = pickup - timedelta(hours=4)
        non_overlap_return = pickup - timedelta(hours=1)
        borrowing = borrowing_services.request_borrowing(
            asset=self.asset,
            borrower=emp_faculty,
            purpose="Morning department seminar",
            requested_start=non_overlap_start,
            requested_return=non_overlap_return,
            created_by=self.faculty
        )
        self.assertIsNotNone(borrowing.pk)
        self.assertEqual(borrowing.status, 'PENDING')

        # Scenario 14c: Approving non-overlapping borrowing succeeds
        approved_borrowing = borrowing_services.approve_borrowing(
            borrowing=borrowing,
            reviewed_by=self.admin
        )
        self.assertEqual(approved_borrowing.status, 'APPROVED')

    # --------------------------------------------------------------------------
    # 15. Asset update form locks condition and updates descriptive metadata
    # --------------------------------------------------------------------------
    def test_asset_update_form_locks_condition_and_updates_descriptive_metadata(self):
        self.client.login(username='admin_integrity', password='Password123!')
        edit_url = reverse('inventory:asset_edit', kwargs={'asset_code': self.asset.asset_code})

        post_data = {
            'item_name': 'Dell Latitude 5420 Updated',
            'category': self.cat_it.pk,
            'brand': self.brand_dell.pk,
            'model': '5420 v2',
            'description': 'Updated specifications and notes',
            'property_number': 'NORSU-CBA-2026-0099',
            'serial_number': 'SN-DELL-998877',
            'acquisition_date': '2026-01-15',
            'acquisition_cost': '48000.00',
            'supplier': 'Dell Official Store',
            'condition': Asset.Condition.POOR,
            'remarks': 'Operational condition verified during audit',
            # Forged lifecycle fields intended to bypass workflow
            'status': Asset.Status.DISPOSED,
            'department': self.dept_ba.pk,
            'current_location': self.loc_ba.pk,
        }

        response = self.client.post(edit_url, post_data)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('inventory:asset_detail', kwargs={'asset_code': self.asset.asset_code}))

        self.asset.refresh_from_db()

        # Legitimate descriptive metadata must be updated
        self.assertEqual(self.asset.item_name, 'Dell Latitude 5420 Updated')
        self.assertEqual(self.asset.model, '5420 v2')
        self.assertEqual(self.asset.description, 'Updated specifications and notes')
        self.assertEqual(self.asset.serial_number, 'SN-DELL-998877')
        self.assertEqual(self.asset.acquisition_cost, Decimal('48000.00'))
        self.assertEqual(self.asset.remarks, 'Operational condition verified during audit')

        # Protected workflow fields and condition must remain strictly unchanged
        self.assertEqual(self.asset.condition, Asset.Condition.GOOD)
        self.assertEqual(self.asset.status, Asset.Status.AVAILABLE)
        self.assertEqual(self.asset.department, self.dept_it)
        self.assertEqual(self.asset.current_location, self.loc_it)
