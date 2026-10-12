from datetime import timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.organizations.models import Department, Location, Employee
from apps.inventory.models import Asset, AssetCategory, Brand, EquipmentType
from apps.student_reservations.models import StudentReservation
from apps.borrowing.models import AssetBorrowing
from apps.maintenance.models import AssetMaintenance
from apps.transfers.models import AssetTransfer
from apps.disposals.models import AssetDisposal
from apps.supplies.models import Supply, SupplyCategory, SupplyTransaction
from apps.audit.models import AuditLog


class DashboardPhase3BBackendTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.now = timezone.now()

        # Departments
        self.dept_ba = Department.objects.create(name='Business Administration', code='BA')
        self.dept_acct = Department.objects.create(name='Accountancy', code='ACCT')

        # Locations
        self.loc_ba = Location.objects.create(name='BA Faculty Room', building='CBA Hall', room_number='101', department=self.dept_ba)
        self.loc_acct = Location.objects.create(name='ACCT Faculty Room', building='CBA Hall', room_number='102', department=self.dept_acct)

        # Users & Roles
        self.admin = User.objects.create_superuser('admin_user', 'admin@cba.edu', 'Pass1234!', role=User.Role.ADMIN)
        self.dean = User.objects.create_user('dean_user', 'dean@cba.edu', 'Pass1234!', role=User.Role.DEAN)
        self.chair_ba = User.objects.create_user('chair_ba', 'chair.ba@cba.edu', 'Pass1234!', role=User.Role.DEPT_CHAIR)
        self.faculty_ba = User.objects.create_user('prof_ba', 'prof.ba@cba.edu', 'Pass1234!', role=User.Role.FACULTY)

        # Employee Profiles
        self.emp_chair_ba = Employee.objects.create(
            user=self.chair_ba,
            employee_id='EMP-CHAIR-BA',
            first_name='Chair',
            last_name='BA',
            department=self.dept_ba,
            location=self.loc_ba,
            is_active=True
        )
        self.emp_faculty_ba = Employee.objects.create(
            user=self.faculty_ba,
            employee_id='EMP-FAC-BA',
            first_name='Prof',
            last_name='BA',
            department=self.dept_ba,
            location=self.loc_ba,
            is_active=True
        )

        # Categories & Brands
        self.cat_it = AssetCategory.objects.create(name='IT Equipment', code='IT', is_active=True, is_reservable=True)
        self.cat_av = AssetCategory.objects.create(name='Audio Visual', code='AV', is_active=True, is_reservable=True)
        self.brand_dell = Brand.objects.create(name='Dell', is_active=True)
        self.brand_epson = Brand.objects.create(name='Epson', is_active=True)

        self.eq_type_projector = EquipmentType.objects.create(name='Projector', category=self.cat_av)

        # Assets in BA
        self.asset_ba_available = Asset.objects.create(
            item_name='BA Laptop 1',
            asset_code='CBA-IT-00001',
            category=self.cat_it,
            brand=self.brand_dell,
            department=self.dept_ba,
            current_location=self.loc_ba,
            condition=Asset.Condition.GOOD,
            status=Asset.Status.AVAILABLE
        )
        # Unserviceable condition asset with status=AVAILABLE (should be excluded from available_assets)
        self.asset_ba_unserviceable = Asset.objects.create(
            item_name='BA Broken Projector',
            asset_code='CBA-AV-00002',
            category=self.cat_av,
            brand=self.brand_epson,
            equipment_type=self.eq_type_projector,
            department=self.dept_ba,
            current_location=self.loc_ba,
            condition=Asset.Condition.UNSERVICEABLE,
            status=Asset.Status.AVAILABLE
        )
        self.asset_ba_assigned = Asset.objects.create(
            item_name='BA Faculty Desktop',
            asset_code='CBA-IT-00003',
            category=self.cat_it,
            brand=self.brand_dell,
            department=self.dept_ba,
            current_location=self.loc_ba,
            condition=Asset.Condition.GOOD,
            status=Asset.Status.ASSIGNED
        )
        self.asset_ba_borrowed = Asset.objects.create(
            item_name='BA Loaner Laptop',
            asset_code='CBA-IT-00004',
            category=self.cat_it,
            brand=self.brand_dell,
            department=self.dept_ba,
            current_location=self.loc_ba,
            condition=Asset.Condition.GOOD,
            status=Asset.Status.BORROWED
        )
        self.asset_ba_maintenance = Asset.objects.create(
            item_name='BA Repair Laptop',
            asset_code='CBA-IT-00005',
            category=self.cat_it,
            brand=self.brand_dell,
            department=self.dept_ba,
            current_location=self.loc_ba,
            condition=Asset.Condition.POOR,
            status=Asset.Status.MAINTENANCE
        )

        # Asset in ACCT
        self.asset_acct_available = Asset.objects.create(
            item_name='ACCT Calculator Set',
            asset_code='CBA-IT-00006',
            category=self.cat_it,
            brand=self.brand_dell,
            department=self.dept_acct,
            current_location=self.loc_acct,
            condition=Asset.Condition.GOOD,
            status=Asset.Status.AVAILABLE
        )

    def test_asset_overview_metrics_admin(self):
        """Admin views college-wide physical asset counts and unserviceable filtering."""
        self.client.login(username='admin_user', password='Pass1234!')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        ctx = response.context

        # Total assets = 5 in BA + 1 in ACCT = 6
        self.assertEqual(ctx['total_assets'], 6)
        # available_assets: status=AVAILABLE and condition!=UNSERVICEABLE
        # asset_ba_available (GOOD), asset_acct_available (GOOD) -> 2
        # asset_ba_unserviceable has condition=UNSERVICEABLE -> excluded from available!
        self.assertEqual(ctx['available_assets'], 2)
        self.assertEqual(ctx['unserviceable_assets'], 1)
        self.assertEqual(ctx['assigned_assets'], 1)
        self.assertEqual(ctx['borrowed_assets'], 1)
        self.assertEqual(ctx['maintenance_assets'], 1)

    def test_asset_overview_metrics_dept_chair(self):
        """Department Chair view is strictly scoped to own department's assets."""
        self.client.login(username='chair_ba', password='Pass1234!')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        ctx = response.context

        # BA has 5 assets; ACCT asset excluded
        self.assertEqual(ctx['total_assets'], 5)
        self.assertEqual(ctx['available_assets'], 1)
        self.assertEqual(ctx['unserviceable_assets'], 1)
        self.assertEqual(ctx['assigned_assets'], 1)
        self.assertEqual(ctx['borrowed_assets'], 1)
        self.assertEqual(ctx['maintenance_assets'], 1)

    def test_operational_queues_student_reservations_and_privacy(self):
        """Pending reservations and guard returns appear in actionable queues with privacy masking."""
        # 1. Pending reservation
        res_pending = StudentReservation.objects.create(
            student_id='2023-00001',
            student_name='Alice Student',
            course_year_section='BSBA 3-A',
            email='alice@student.cba.edu',
            contact_number='09171234567',
            category=self.cat_av,
            requested_pickup=self.now + timedelta(hours=2),
            requested_return=self.now + timedelta(hours=5),
            purpose='Class Presentation',
            status=StudentReservation.Status.PENDING
        )

        # 2. Guard return pending inspection
        res_guard = StudentReservation.objects.create(
            student_id='2023-00002',
            student_name='Bob Student',
            course_year_section='BSBA 4-B',
            email='bob@student.cba.edu',
            contact_number='09187654321',
            category=self.cat_av,
            asset=self.asset_ba_available,
            requested_pickup=self.now - timedelta(hours=6),
            requested_return=self.now - timedelta(hours=2),
            purpose='Club Meeting',
            status=StudentReservation.Status.RETURNED_TO_GUARD,
            guard_returned_at=self.now - timedelta(hours=1),
            guard_recorded_by=self.admin
        )

        # 3. Released active student loan
        res_released = StudentReservation.objects.create(
            student_id='2023-00003',
            student_name='Charlie Student',
            category=self.cat_it,
            asset=self.asset_ba_borrowed,
            requested_pickup=self.now - timedelta(hours=1),
            requested_return=self.now + timedelta(hours=3),
            purpose='Research Lab',
            status=StudentReservation.Status.RELEASED,
            released_by=self.admin,
            released_at=self.now - timedelta(hours=1)
        )

        # Non-custodian (Dean): actionable student queues restricted to custodians
        self.client.login(username='dean_user', password='Pass1234!')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        ctx = response.context

        # Non-custodians receive 0 / empty list for student reservation queues
        self.assertEqual(ctx['pending_reservations_count'], 0)
        self.assertEqual(ctx['pending_reservations_list'], [])
        self.assertEqual(ctx['guard_returns_count'], 0)
        self.assertEqual(ctx['guard_returns_list'], [])
        # Overview metric preserved
        self.assertEqual(ctx['student_active_loans_count'], 1)

        # Direct test of mask_contact_info helper
        from apps.student_reservations.security import mask_contact_info
        m_email, m_phone = mask_contact_info(res_pending.email, res_pending.contact_number)
        self.assertNotEqual(m_email, 'alice@student.cba.edu')
        self.assertIn('***', m_email)
        self.assertNotEqual(m_phone, '09171234567')
        self.assertIn('****', m_phone)

        m_guard_email, m_guard_phone = mask_contact_info(res_guard.email, res_guard.contact_number)
        self.assertNotEqual(m_guard_email, 'bob@student.cba.edu')
        self.assertIn('***', m_guard_email)
        self.assertNotEqual(m_guard_phone, '09187654321')
        self.assertIn('****', m_guard_phone)

        # Custodian (Admin): actionable queues populated with original unmasked data
        self.client.login(username='admin_user', password='Pass1234!')
        response_admin = self.client.get(reverse('dashboard'))
        ctx_admin = response_admin.context
        self.assertEqual(ctx_admin['pending_reservations_count'], 1)
        self.assertEqual(ctx_admin['guard_returns_count'], 1)
        self.assertEqual(ctx_admin['student_active_loans_count'], 1)
        admin_pending_item = ctx_admin['pending_reservations_list'][0]
        self.assertEqual(admin_pending_item.email, 'alice@student.cba.edu')
        self.assertEqual(admin_pending_item.contact_number, '09171234567')

    def test_overdue_loans_distinct_combined_queue(self):
        """Overdue loans correctly combines faculty borrowings and student reservations without double-counting."""
        # 1. Overdue faculty borrowing (status=RELEASED, requested_return in past)
        borrowing_overdue = AssetBorrowing.objects.create(
            asset=self.asset_ba_available,
            borrower=self.emp_faculty_ba,
            borrower_department=self.dept_ba,
            purpose='Lecture',
            requested_start=self.now - timedelta(hours=5),
            requested_return=self.now - timedelta(hours=2),
            status=AssetBorrowing.Status.RELEASED,
            released_by=self.admin
        )

        # 2. Overdue student reservation (status=RELEASED, requested_return in past)
        student_overdue = StudentReservation.objects.create(
            student_id='2023-00009',
            student_name='David Student',
            email='david@student.cba.edu',
            contact_number='09199998888',
            category=self.cat_it,
            asset=self.asset_ba_assigned,
            requested_pickup=self.now - timedelta(hours=6),
            requested_return=self.now - timedelta(hours=3),
            purpose='Case Study',
            status=StudentReservation.Status.RELEASED,
            released_by=self.admin,
            released_at=self.now - timedelta(hours=6)
        )

        self.client.login(username='admin_user', password='Pass1234!')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        ctx = response.context

        # Exactly 2 overdue loans: 1 faculty + 1 student
        self.assertEqual(ctx['overdue_loans_count'], 2)
        self.assertEqual(ctx['overdue_borrowings_count'], 2)
        self.assertEqual(len(ctx['overdue_loans_list']), 2)

        # Sorted by requested_return ascending: student (due -3h) before faculty (due -2h)
        first_overdue = ctx['overdue_loans_list'][0]
        second_overdue = ctx['overdue_loans_list'][1]
        self.assertEqual(first_overdue.loan_type, 'STUDENT')
        self.assertEqual(first_overdue.borrower_name, 'David Student')
        self.assertEqual(second_overdue.loan_type, 'FACULTY')
        self.assertEqual(second_overdue.borrower_name, 'Prof BA')

    def test_open_maintenance_and_critical_severity(self):
        """Open maintenance cases (REPORTED, ASSESSED) and critical severity counters."""
        case_reported = AssetMaintenance.objects.create(
            asset=self.asset_ba_maintenance,
            issue_title='Screen Flickering',
            issue_description='Display flashes continuously during startup',
            reported_by=self.admin,
            status=AssetMaintenance.Status.REPORTED,
            severity=AssetMaintenance.Severity.MEDIUM
        )
        case_critical = AssetMaintenance.objects.create(
            asset=self.asset_ba_unserviceable,
            issue_title='Power Supply Blown',
            issue_description='Smoke detected on power up in conference hall',
            reported_by=self.admin,
            status=AssetMaintenance.Status.ASSESSED,
            severity=AssetMaintenance.Severity.CRITICAL
        )
        # Completed case (should not be in open maintenance queue)
        case_completed = AssetMaintenance.objects.create(
            asset=self.asset_ba_available,
            issue_title='Cable Replaced',
            issue_description='Replaced HDMI cable',
            reported_by=self.admin,
            status=AssetMaintenance.Status.COMPLETED,
            severity=AssetMaintenance.Severity.LOW,
            final_condition=Asset.Condition.GOOD
        )

        self.client.login(username='admin_user', password='Pass1234!')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        ctx = response.context

        # 2 open cases (REPORTED + ASSESSED)
        self.assertEqual(ctx['open_maintenance_count'], 2)
        self.assertEqual(ctx['critical_maintenance_count'], 1)
        self.assertEqual(len(ctx['open_maintenance_list']), 2)

    def test_pending_transfers_count(self):
        """Transfers in PENDING or APPROVED statuses are surfaced in operational attention queue."""
        transfer_pending = AssetTransfer.objects.create(
            asset=self.asset_ba_available,
            from_department=self.dept_ba,
            to_department=self.dept_acct,
            reason='Inter-department loan',
            status=AssetTransfer.Status.PENDING,
            requested_by=self.admin
        )
        transfer_completed = AssetTransfer.objects.create(
            asset=self.asset_acct_available,
            from_department=self.dept_acct,
            to_department=self.dept_ba,
            reason='Permanent transfer',
            status=AssetTransfer.Status.COMPLETED,
            requested_by=self.admin
        )

        self.client.login(username='admin_user', password='Pass1234!')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        ctx = response.context

        self.assertEqual(ctx['pending_transfers_count'], 1)

    def test_consumable_supplies_health(self):
        """Consumables low stock and depleted stock counts correctly derived."""
        sup_cat = SupplyCategory.objects.create(name='Stationery', code='STAT')
        supply_nominal = Supply.objects.create(
            item_name='Whiteboard Marker',
            category=sup_cat,
            reorder_level=5
        )
        supply_depleted = Supply.objects.create(
            item_name='Thermal Paper Roll',
            category=sup_cat,
            reorder_level=10
        )

        # Stock nominal: add 20 units
        SupplyTransaction.objects.create(
            supply=supply_nominal,
            transaction_type=SupplyTransaction.TransactionType.STOCK_IN,
            quantity=20,
            processed_by=self.admin,
            transaction_date=self.now.date()
        )

        # supply_depleted has 0 stock (below reorder_level 10 and depleted <= 0)
        self.client.login(username='admin_user', password='Pass1234!')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        ctx = response.context

        self.assertEqual(ctx['low_stock_supplies_count'], 1)
        self.assertEqual(ctx['out_of_stock_supplies_count'], 1)

    def test_read_only_safety_no_database_mutations(self):
        """Dashboard querysets are strictly read-only and do not mutate statuses."""
        borrowing_released = AssetBorrowing.objects.create(
            asset=self.asset_ba_available,
            borrower=self.emp_faculty_ba,
            borrower_department=self.dept_ba,
            purpose='Lecture',
            requested_start=self.now - timedelta(hours=4),
            requested_return=self.now - timedelta(hours=1),
            status=AssetBorrowing.Status.RELEASED,
            released_by=self.admin
        )

        # Request dashboard
        self.client.login(username='admin_user', password='Pass1234!')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

        # Database record must NOT be mutated by DashboardView.get_context_data()
        borrowing_released.refresh_from_db()
        self.assertEqual(
            borrowing_released.status,
            AssetBorrowing.Status.RELEASED,
            "DashboardView must remain strictly read-only and NOT mutate records."
        )

    def test_asset_overview_full_metrics_including_damaged_and_on_loan_breakdown(self):
        """Dashboard accurately breaks down on-loan physical assets and tracks damaged status."""
        # 1. Damaged asset
        Asset.objects.create(
            item_name='BA Damaged Printer',
            asset_code='CBA-IT-00007',
            category=self.cat_it,
            brand=self.brand_dell,
            department=self.dept_ba,
            current_location=self.loc_ba,
            condition=Asset.Condition.POOR,
            status=Asset.Status.DAMAGED
        )

        # 2. Student active loan (RELEASED)
        StudentReservation.objects.create(
            student_id='2023-00010',
            student_name='Eve Student',
            category=self.cat_it,
            asset=self.asset_ba_available,
            requested_pickup=self.now - timedelta(hours=1),
            requested_return=self.now + timedelta(hours=2),
            purpose='Class Project',
            status=StudentReservation.Status.RELEASED,
            released_by=self.admin,
            released_at=self.now - timedelta(hours=1)
        )

        self.client.login(username='admin_user', password='Pass1234!')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        ctx = response.context

        # 6 baseline assets + 1 damaged = 7
        self.assertEqual(ctx['total_assets'], 7)
        self.assertEqual(ctx['available_assets'], 2)
        self.assertEqual(ctx['unserviceable_assets'], 1)
        self.assertEqual(ctx['assigned_assets'], 1)
        self.assertEqual(ctx['borrowed_assets'], 1)  # Staff borrowing
        self.assertEqual(ctx['student_active_loans_count'], 1)  # Student active loan
        self.assertEqual(ctx['total_on_loan_assets'], 2)  # Staff + Student
        self.assertEqual(ctx['total_physical_on_loan'], 2)
        self.assertEqual(ctx['maintenance_assets'], 1)
        self.assertEqual(ctx['damaged_assets'], 1)

    def test_dept_chair_comprehensive_queue_scoping(self):
        """Department Chair view strictly isolates student queues, maintenance, transfers, and charts."""
        # 1. Pending reservations: 1 BA, 1 ACCT, 1 unassigned
        res_ba = StudentReservation.objects.create(
            student_id='2023-00021',
            student_name='Student BA',
            email='s_ba@student.cba.edu',
            contact_number='09170001111',
            category=self.cat_it,
            asset=self.asset_ba_available,
            requested_pickup=self.now + timedelta(hours=1),
            requested_return=self.now + timedelta(hours=3),
            purpose='BA Defense',
            status=StudentReservation.Status.PENDING
        )
        res_acct = StudentReservation.objects.create(
            student_id='2023-00022',
            student_name='Student ACCT',
            email='s_acct@student.cba.edu',
            contact_number='09170002222',
            category=self.cat_it,
            asset=self.asset_acct_available,
            requested_pickup=self.now + timedelta(hours=1),
            requested_return=self.now + timedelta(hours=3),
            purpose='ACCT Audit',
            status=StudentReservation.Status.PENDING
        )
        res_unassigned = StudentReservation.objects.create(
            student_id='2023-00023',
            student_name='Student Unassigned',
            email='s_unass@student.cba.edu',
            contact_number='09170003333',
            category=self.cat_it,
            asset=None,
            requested_pickup=self.now + timedelta(hours=1),
            requested_return=self.now + timedelta(hours=3),
            purpose='General Seminar',
            status=StudentReservation.Status.PENDING
        )

        # 2. Guard returns: 1 BA, 1 ACCT
        StudentReservation.objects.create(
            student_id='2023-00024',
            student_name='Guard Return BA',
            category=self.cat_it,
            asset=self.asset_ba_available,
            requested_pickup=self.now - timedelta(hours=4),
            requested_return=self.now - timedelta(hours=1),
            purpose='BA Lab',
            status=StudentReservation.Status.RETURNED_TO_GUARD,
            guard_returned_at=self.now - timedelta(minutes=30),
            guard_recorded_by=self.admin
        )
        StudentReservation.objects.create(
            student_id='2023-00025',
            student_name='Guard Return ACCT',
            category=self.cat_it,
            asset=self.asset_acct_available,
            requested_pickup=self.now - timedelta(hours=4),
            requested_return=self.now - timedelta(hours=1),
            purpose='ACCT Lab',
            status=StudentReservation.Status.RETURNED_TO_GUARD,
            guard_returned_at=self.now - timedelta(minutes=30),
            guard_recorded_by=self.admin
        )

        # 3. Overdue borrowings: 1 BA, 1 ACCT
        emp_acct = Employee.objects.create(
            user=self.admin,
            employee_id='EMP-ACCT-01',
            first_name='Prof',
            last_name='ACCT',
            department=self.dept_acct,
            location=self.loc_acct,
            is_active=True
        )
        AssetBorrowing.objects.create(
            asset=self.asset_ba_available,
            borrower=self.emp_faculty_ba,
            borrower_department=self.dept_ba,
            purpose='BA Lecture',
            requested_start=self.now - timedelta(hours=3),
            requested_return=self.now - timedelta(hours=1),
            status=AssetBorrowing.Status.RELEASED,
            released_by=self.admin
        )
        AssetBorrowing.objects.create(
            asset=self.asset_acct_available,
            borrower=emp_acct,
            borrower_department=self.dept_acct,
            purpose='ACCT Lecture',
            requested_start=self.now - timedelta(hours=3),
            requested_return=self.now - timedelta(hours=1),
            status=AssetBorrowing.Status.RELEASED,
            released_by=self.admin
        )

        # 4. Overdue student loan: 1 BA, 1 ACCT
        StudentReservation.objects.create(
            student_id='2023-00026',
            student_name='Student Overdue BA',
            category=self.cat_it,
            asset=self.asset_ba_assigned,
            requested_pickup=self.now - timedelta(hours=5),
            requested_return=self.now - timedelta(hours=2),
            purpose='BA Study',
            status=StudentReservation.Status.RELEASED,
            released_by=self.admin
        )
        asset_acct_2 = Asset.objects.create(
            item_name='ACCT Calculator Set 2',
            asset_code='CBA-IT-00033',
            category=self.cat_it,
            brand=self.brand_dell,
            department=self.dept_acct,
            current_location=self.loc_acct,
            condition=Asset.Condition.GOOD,
            status=Asset.Status.BORROWED
        )
        StudentReservation.objects.create(
            student_id='2023-00027',
            student_name='Student Overdue ACCT',
            category=self.cat_it,
            asset=asset_acct_2,
            requested_pickup=self.now - timedelta(hours=5),
            requested_return=self.now - timedelta(hours=2),
            purpose='ACCT Study',
            status=StudentReservation.Status.RELEASED,
            released_by=self.admin
        )

        # 5. Open Maintenance: 1 BA, 1 ACCT
        AssetMaintenance.objects.create(
            asset=self.asset_ba_maintenance,
            issue_title='BA Maintenance Issue',
            reported_by=self.admin,
            status=AssetMaintenance.Status.REPORTED,
            severity=AssetMaintenance.Severity.HIGH
        )
        AssetMaintenance.objects.create(
            asset=self.asset_acct_available,
            issue_title='ACCT Maintenance Issue',
            reported_by=self.admin,
            status=AssetMaintenance.Status.REPORTED,
            severity=AssetMaintenance.Severity.HIGH
        )

        # 6. Transfers: 1 BA (from BA), 1 ACCT (from ACCT to another)
        dept_other = Department.objects.create(name='Marketing', code='MKT')
        AssetTransfer.objects.create(
            asset=self.asset_ba_available,
            from_department=self.dept_ba,
            to_department=dept_other,
            reason='BA transfer',
            status=AssetTransfer.Status.PENDING,
            requested_by=self.admin
        )
        AssetTransfer.objects.create(
            asset=self.asset_acct_available,
            from_department=self.dept_acct,
            to_department=dept_other,
            reason='ACCT transfer',
            status=AssetTransfer.Status.PENDING,
            requested_by=self.admin
        )

        # 7. Disposals: 1 BA, 1 ACCT
        AssetDisposal.objects.create(
            asset=self.asset_ba_unserviceable,
            reason='Beyond repair',
            disposal_method=AssetDisposal.DisposalMethod.SCRAP,
            status=AssetDisposal.Status.PENDING,
            requested_by=self.admin
        )
        asset_acct_scrap = Asset.objects.create(
            item_name='ACCT Old Calculator',
            asset_code='CBA-IT-00008',
            category=self.cat_it,
            brand=self.brand_dell,
            department=self.dept_acct,
            current_location=self.loc_acct,
            condition=Asset.Condition.UNSERVICEABLE,
            status=Asset.Status.AVAILABLE
        )
        AssetDisposal.objects.create(
            asset=asset_acct_scrap,
            reason='ACCT scrap',
            disposal_method=AssetDisposal.DisposalMethod.SCRAP,
            status=AssetDisposal.Status.PENDING,
            requested_by=self.admin
        )

        # Login as BA Chair
        self.client.login(username='chair_ba', password='Pass1234!')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        ctx = response.context

        # Scoping verifications for Dept Chair (non-custodian)
        # Actionable student reservation and guard-return queues restricted to custodians
        self.assertEqual(ctx['pending_reservations_count'], 0)
        self.assertEqual(ctx['pending_reservations_list'], [])
        self.assertEqual(ctx['guard_returns_count'], 0)
        self.assertEqual(ctx['guard_returns_list'], [])
        # Overdue loans for non-custodian includes department faculty borrowings (excludes student loans)
        self.assertEqual(ctx['overdue_loans_count'], 1)  # 1 BA faculty (ACCT excluded)
        self.assertEqual(ctx['open_maintenance_count'], 1)  # Only BA maintenance
        self.assertEqual(ctx['pending_transfers_count'], 1)  # Only BA transfer
        self.assertEqual(ctx['pending_disposals_count'], 1)  # Only BA disposal

        # Chart title scoping
        self.assertIn('Assets by Location', ctx['department_chart_title'])
        self.assertIn('Business Administration', ctx['department_chart_title'])
        self.assertIn(self.loc_ba.name, ctx['department_chart_labels'])

    def test_dean_college_wide_visibility_and_privacy(self):
        """Dean sees college-wide inventory overview, but actionable student queues are restricted to custodians."""
        StudentReservation.objects.create(
            student_id='2023-00030',
            student_name='Dean Test Student',
            email='dean_student@student.cba.edu',
            contact_number='09175554321',
            category=self.cat_it,
            asset=self.asset_acct_available,
            requested_pickup=self.now + timedelta(hours=2),
            requested_return=self.now + timedelta(hours=4),
            purpose='Dean Case Study',
            status=StudentReservation.Status.PENDING
        )

        self.client.login(username='dean_user', password='Pass1234!')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        ctx = response.context

        # College-wide assets and overview stats
        self.assertEqual(ctx['total_assets'], 6)
        self.assertEqual(ctx['department_chart_title'], 'Assets by Department')
        self.assertIn('Business Administration', ctx['department_chart_labels'])
        self.assertIn('Accountancy', ctx['department_chart_labels'])

        # Non-custodian Dean receives 0/empty for actionable student queue
        self.assertEqual(ctx['pending_reservations_count'], 0)
        self.assertEqual(ctx['pending_reservations_list'], [])
        self.assertFalse(ctx['is_custodian'])

        # Custodian (Admin) sees the actionable pending reservation
        self.client.login(username='admin_user', password='Pass1234!')
        response_admin = self.client.get(reverse('dashboard'))
        ctx_admin = response_admin.context
        self.assertEqual(ctx_admin['pending_reservations_count'], 1)
        self.assertTrue(ctx_admin['is_custodian'])
        self.assertEqual(len(ctx_admin['pending_reservations_list']), 1)

    def test_faculty_dashboard_restrictions_and_personal_queues(self):
        """Faculty cannot see administrative queues or charts, but sees own borrowings and maintenance."""
        # Administrative queue items
        StudentReservation.objects.create(
            student_id='2023-00040',
            student_name='Student Admin Queue',
            email='admin_queue@student.cba.edu',
            contact_number='09178881234',
            category=self.cat_it,
            requested_pickup=self.now + timedelta(hours=1),
            requested_return=self.now + timedelta(hours=3),
            purpose='Presentation',
            status=StudentReservation.Status.PENDING
        )
        AssetTransfer.objects.create(
            asset=self.asset_ba_available,
            from_department=self.dept_ba,
            to_department=self.dept_acct,
            reason='Test Transfer',
            status=AssetTransfer.Status.PENDING,
            requested_by=self.admin
        )
        AssetDisposal.objects.create(
            asset=self.asset_ba_unserviceable,
            reason='Broken',
            disposal_method=AssetDisposal.DisposalMethod.SCRAP,
            status=AssetDisposal.Status.PENDING,
            requested_by=self.admin
        )

        # Faculty's own overdue loan
        b_fac = AssetBorrowing.objects.create(
            asset=self.asset_ba_available,
            borrower=self.emp_faculty_ba,
            borrower_department=self.dept_ba,
            purpose='Faculty Lecture',
            requested_start=self.now - timedelta(hours=4),
            requested_return=self.now - timedelta(hours=1),
            status=AssetBorrowing.Status.RELEASED,
            released_by=self.admin
        )
        # Another user's overdue loan
        AssetBorrowing.objects.create(
            asset=self.asset_ba_assigned,
            borrower=self.emp_chair_ba,
            borrower_department=self.dept_ba,
            purpose='Chair Meeting',
            requested_start=self.now - timedelta(hours=4),
            requested_return=self.now - timedelta(hours=1),
            status=AssetBorrowing.Status.RELEASED,
            released_by=self.admin
        )

        # Faculty's own maintenance report
        AssetMaintenance.objects.create(
            asset=self.asset_ba_maintenance,
            issue_title='Faculty Reported Issue',
            reported_by=self.faculty_ba,
            status=AssetMaintenance.Status.REPORTED,
            severity=AssetMaintenance.Severity.LOW
        )
        # Another user's maintenance report
        AssetMaintenance.objects.create(
            asset=self.asset_ba_unserviceable,
            issue_title='Admin Reported Issue',
            reported_by=self.admin,
            status=AssetMaintenance.Status.REPORTED,
            severity=AssetMaintenance.Severity.CRITICAL
        )

        self.client.login(username='prof_ba', password='Pass1234!')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        ctx = response.context

        # Faculty restricted from staff queues
        self.assertEqual(ctx['pending_reservations_count'], 0)
        self.assertEqual(ctx['pending_reservations_list'], [])
        self.assertEqual(ctx['guard_returns_count'], 0)
        self.assertEqual(ctx['guard_returns_list'], [])
        self.assertEqual(ctx['student_active_loans_count'], 0)
        self.assertEqual(ctx['pending_transfers_count'], 0)
        self.assertEqual(ctx['pending_transfers_list'], [])
        self.assertEqual(ctx['pending_disposals_count'], 0)

        # Faculty sees ONLY their own overdue loan
        self.assertEqual(ctx['overdue_loans_count'], 1)
        self.assertEqual(len(ctx['overdue_loans_list']), 1)
        self.assertEqual(ctx['overdue_loans_list'][0].pk, b_fac.pk)
        self.assertEqual(ctx['overdue_loans_list'][0].borrower_name, self.emp_faculty_ba.full_name)

        # Faculty sees ONLY their own reported maintenance
        self.assertEqual(ctx['open_maintenance_count'], 1)
        self.assertEqual(len(ctx['open_maintenance_list']), 1)
        self.assertEqual(ctx['open_maintenance_list'][0].reported_by, self.faculty_ba)

        # Charts strictly omitted for faculty
        self.assertEqual(ctx['category_chart_labels'], [])
        self.assertEqual(ctx['condition_chart_labels'], [])
        self.assertEqual(ctx['department_chart_labels'], [])

    def test_overdue_borrowing_comprehensive_status_matrix(self):
        """Verifies exact status and timestamp combinations determining overdue state."""
        # 1. status=OVERDUE, requested_return in past -> Overdue
        b1 = AssetBorrowing.objects.create(
            asset=self.asset_ba_available,
            borrower=self.emp_faculty_ba,
            borrower_department=self.dept_ba,
            purpose='Lecture 1',
            requested_start=self.now - timedelta(days=2),
            requested_return=self.now - timedelta(days=1),
            status=AssetBorrowing.Status.OVERDUE,
            released_by=self.admin
        )
        # 2. status=OVERDUE, requested_return in future -> Overdue
        b2 = AssetBorrowing.objects.create(
            asset=self.asset_ba_assigned,
            borrower=self.emp_faculty_ba,
            borrower_department=self.dept_ba,
            purpose='Lecture 2',
            requested_start=self.now - timedelta(hours=1),
            requested_return=self.now + timedelta(hours=2),
            status=AssetBorrowing.Status.OVERDUE,
            released_by=self.admin
        )
        # 3. status=RELEASED, requested_return in past -> Overdue
        b3 = AssetBorrowing.objects.create(
            asset=self.asset_ba_borrowed,
            borrower=self.emp_faculty_ba,
            borrower_department=self.dept_ba,
            purpose='Lecture 3',
            requested_start=self.now - timedelta(hours=5),
            requested_return=self.now - timedelta(hours=1),
            status=AssetBorrowing.Status.RELEASED,
            released_by=self.admin
        )
        # 4. status=RELEASED, requested_return in future -> NOT overdue
        b4 = AssetBorrowing.objects.create(
            asset=self.asset_ba_maintenance,
            borrower=self.emp_faculty_ba,
            borrower_department=self.dept_ba,
            purpose='Lecture 4',
            requested_start=self.now - timedelta(hours=1),
            requested_return=self.now + timedelta(hours=3),
            status=AssetBorrowing.Status.RELEASED,
            released_by=self.admin
        )
        # 5. status=RETURNED, requested_return in past -> NOT overdue
        b5 = AssetBorrowing.objects.create(
            asset=self.asset_acct_available,
            borrower=self.emp_faculty_ba,
            borrower_department=self.dept_ba,
            purpose='Lecture 5',
            requested_start=self.now - timedelta(days=3),
            requested_return=self.now - timedelta(days=2),
            status=AssetBorrowing.Status.RETURNED,
            released_by=self.admin,
            returned_at=self.now - timedelta(days=1)
        )
        # 6. status=APPROVED, requested_return in past -> NOT overdue (not released)
        b6 = AssetBorrowing.objects.create(
            asset=self.asset_ba_available,
            borrower=self.emp_faculty_ba,
            borrower_department=self.dept_ba,
            purpose='Lecture 6',
            requested_start=self.now - timedelta(days=2),
            requested_return=self.now - timedelta(days=1),
            status=AssetBorrowing.Status.APPROVED,
            reviewed_by=self.admin
        )

        self.client.login(username='admin_user', password='Pass1234!')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        ctx = response.context

        # Exactly b1, b2, b3 are overdue = 3
        self.assertEqual(ctx['overdue_loans_count'], 3)
        overdue_pks = [item.pk for item in ctx['overdue_loans_list']]
        self.assertIn(b1.pk, overdue_pks)
        self.assertIn(b2.pk, overdue_pks)
        self.assertIn(b3.pk, overdue_pks)
        self.assertNotIn(b4.pk, overdue_pks)
        self.assertNotIn(b5.pk, overdue_pks)
        self.assertNotIn(b6.pk, overdue_pks)

    def test_public_student_portal_and_lifecycle_immutability(self):
        """Student reservation portal routes remain accessible and no asset lifecycles are mutated."""
        # Public catalog route accessible anonymously
        catalog_resp = self.client.get(reverse('student_reservations:catalog'))
        self.assertEqual(catalog_resp.status_code, 200)

        # Public request route accessible anonymously
        request_resp = self.client.get(reverse('student_reservations:public_request'))
        self.assertEqual(request_resp.status_code, 200)

        # Public lookup search route accessible anonymously
        lookup_resp = self.client.get(reverse('student_reservations:public_lookup_search'))
        self.assertEqual(lookup_resp.status_code, 200)

        # Verify initial asset status and condition are unmutated
        self.asset_ba_available.refresh_from_db()
        self.assertEqual(self.asset_ba_available.status, Asset.Status.AVAILABLE)
        self.assertEqual(self.asset_ba_available.condition, Asset.Condition.GOOD)

        self.asset_ba_unserviceable.refresh_from_db()
        self.assertEqual(self.asset_ba_unserviceable.status, Asset.Status.AVAILABLE)
        self.assertEqual(self.asset_ba_unserviceable.condition, Asset.Condition.UNSERVICEABLE)
