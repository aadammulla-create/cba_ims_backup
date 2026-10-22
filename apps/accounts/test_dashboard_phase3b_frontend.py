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


class DashboardFrontendPhase3BTests(TestCase):
    """
    Validates frontend template rendering for Phase 3B:
    1. Unified 7-section Sidebar Navigation in sidebar_nav.html
    2. Staff Dashboard hierarchy, KPI cards, operational queues, and empty state
    """
    def setUp(self):
        self.client = Client()
        self.now = timezone.now()

        # Departments & Locations
        self.dept = Department.objects.create(name='Business Administration', code='BA')
        self.loc = Location.objects.create(name='BA Office', department=self.dept)

        # Users
        self.admin = User.objects.create_superuser('admin_fe', 'admin_fe@cba.edu', 'Pass1234!', role=User.Role.ADMIN)
        self.dean = User.objects.create_user('dean_fe', 'dean_fe@cba.edu', 'Pass1234!', role=User.Role.DEAN)
        self.chair = User.objects.create_user('chair_fe', 'chair_fe@cba.edu', 'Pass1234!', role=User.Role.DEPT_CHAIR)
        self.faculty = User.objects.create_user('fac_fe', 'fac_fe@cba.edu', 'Pass1234!', role=User.Role.FACULTY)

        # Employees
        self.emp_admin = Employee.objects.create(
            user=self.admin,
            employee_id='EMP-ADM-01',
            first_name='Admin',
            last_name='User',
            department=self.dept,
            location=self.loc
        )
        self.emp_chair = Employee.objects.create(
            user=self.chair,
            employee_id='EMP-CHR-01',
            first_name='Chair',
            last_name='User',
            department=self.dept,
            location=self.loc
        )
        self.emp_fac = Employee.objects.create(
            user=self.faculty,
            employee_id='EMP-FAC-01',
            first_name='Faculty',
            last_name='User',
            department=self.dept,
            location=self.loc
        )

        # Category & Asset
        self.cat = AssetCategory.objects.create(name='IT Equipment', code='IT', is_active=True, is_reservable=True)
        self.asset = Asset.objects.create(
            item_name='Test Laptop',
            asset_code='CBA-IT-00099',
            category=self.cat,
            department=self.dept,
            current_location=self.loc,
            condition=Asset.Condition.GOOD,
            status=Asset.Status.AVAILABLE
        )

    def test_sidebar_sections_rendered_for_admin(self):
        """Admin should see all approved primary navigation sections and management tool groups in sidebar."""
        self.client.force_login(self.admin)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Check primary section headers and management tool group labels
        self.assertIn('Overview &amp; Queues', content)
        self.assertIn('Management Tools', content)
        self.assertIn('Inventory Tools', content)
        self.assertIn('Asset Operations', content)
        self.assertIn('Supplies', content)
        self.assertIn('Administration', content)

        # Check specific key links
        self.assertIn(reverse('inventory:asset_list'), content)
        self.assertIn(reverse('inventory:asset_scan'), content)
        self.assertIn(reverse('inventory:category_list'), content)
        self.assertIn(reverse('inventory:physical_verification_list'), content)
        self.assertIn(reverse('organizations:location_list'), content)
        self.assertIn(reverse('inventory:qr_labels_bulk'), content)
        self.assertIn(reverse('student_reservations:custodian_list'), content)
        self.assertIn(reverse('borrowing:active_list'), content)
        self.assertIn(reverse('assignments:current_list'), content)
        self.assertIn(reverse('transfers:pending_list'), content)
        self.assertIn(reverse('maintenance:case_list'), content)
        self.assertIn(reverse('disposals:pending_list'), content)
        self.assertIn(reverse('supplies:supply_list'), content)
        self.assertIn(reverse('reports:reports_dashboard'), content)
        self.assertIn(reverse('audit:audit_log_list'), content)
        self.assertIn(reverse('organizations:employee_list'), content)
        self.assertIn(reverse('organizations:department_list'), content)
        self.assertIn(reverse('accounts:user_list'), content)

    def test_sidebar_role_filtering_for_faculty(self):
        """Faculty user should see personal workspace tools and not restricted administrative sections."""
        self.client.force_login(self.faculty)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Faculty sees My Workspace, Reference & Directory, and personal actions
        self.assertIn('My Workspace', content)
        self.assertIn('Reference &amp; Directory', content)
        self.assertIn('Directory', content)
        self.assertIn(reverse('dashboard'), content)
        self.assertIn(reverse('inventory:asset_scan'), content)
        self.assertIn(reverse('borrowing:my_borrowings'), content)
        self.assertIn(reverse('assignments:my_accountability'), content)
        self.assertIn(reverse('maintenance:my_reports'), content)
        self.assertIn(reverse('borrowing:request_create'), content)
        self.assertIn(reverse('maintenance:report_create'), content)

        # Faculty must NOT see admin/custodian links or management headers
        self.assertNotIn('Overview &amp; Queues', content)
        self.assertNotIn('Management Tools', content)
        self.assertNotIn('Asset Register', content)
        self.assertNotIn('Bulk QR Labels', content)
        self.assertNotIn('Student Reservations', content)
        self.assertNotIn('Audit History', content)
        self.assertNotIn(f'href="{reverse("student_reservations:custodian_list")}"', content)
        self.assertNotIn(f'href="{reverse("accounts:user_list")}"', content)
        self.assertNotIn(f'href="{reverse("audit:audit_log_list")}"', content)

        # Sidebar navigation specifically excludes Asset Register
        sidebar_start = content.find('class="sidebar-nav"')
        sidebar_end = content.find('<!-- Main Content Area -->')
        sidebar_content = content[sidebar_start:sidebar_end] if sidebar_start != -1 else content
        self.assertNotIn(f'href="{reverse("inventory:asset_list")}"', sidebar_content)

    def test_dashboard_empty_state_when_queues_clear(self):
        """When no items require attention, the professional empty state is rendered."""
        self.client.force_login(self.admin)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Empty state message
        self.assertIn('All operational queues are clear. No pending items require immediate attention.', content)

    def test_dashboard_operational_queues_rendered_when_active(self):
        """When attention items exist, the operational queue panel with tabs and action buttons is rendered."""
        # Create a pending student reservation
        res = StudentReservation.objects.create(
            student_id='2026-1001',
            student_name='Alice Student',
            category=self.cat,
            requested_pickup=self.now + timezone.timedelta(hours=2),
            requested_return=self.now + timezone.timedelta(hours=4),
            purpose='Academic defense',
            status=StudentReservation.Status.PENDING
        )

        # Create a low stock supply
        scat = SupplyCategory.objects.create(name='Paper', code='PPR')
        supply = Supply.objects.create(
            item_name='Bond Paper A4',
            category=scat,
            reorder_level=10,
            unit=Supply.Unit.REAM
        )
        SupplyTransaction.objects.create(
            supply=supply,
            transaction_type=SupplyTransaction.TransactionType.STOCK_IN,
            quantity=5,
            processed_by=self.admin
        )

        self.client.force_login(self.admin)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Live Operational Queues panel rendered
        self.assertIn('Live Operational Queues', content)
        self.assertIn('Student Reservations', content)
        self.assertIn('Low Supplies', content)

        # Action buttons rendered
        self.assertIn('Review', content)
        self.assertIn('Stock In', content)
        self.assertIn(res.student_name, content)
        self.assertIn(supply.item_name, content)

    def test_sidebar_links_for_dean_and_dept_chair(self):
        """Dean and Dept Chair see staff menus but are excluded from custodian-only and admin-only links."""
        # Test Dean
        self.client.force_login(self.dean)
        resp_dean = self.client.get(reverse('dashboard'))
        self.assertEqual(resp_dean.status_code, 200)
        c_dean = resp_dean.content.decode('utf-8')

        # Dean sees inventory, supplies, reports, organizations
        self.assertIn(reverse('inventory:asset_list'), c_dean)
        self.assertIn(reverse('supplies:supply_list'), c_dean)
        self.assertIn(reverse('reports:reports_dashboard'), c_dean)
        self.assertIn(reverse('organizations:employee_list'), c_dean)
        self.assertIn(reverse('organizations:department_list'), c_dean)

        # Dean does NOT see custodian-only or admin-only links
        self.assertNotIn(reverse('student_reservations:custodian_list'), c_dean)
        self.assertNotIn(reverse('inventory:qr_labels_bulk'), c_dean)
        self.assertNotIn(reverse('audit:audit_log_list'), c_dean)
        self.assertNotIn(reverse('accounts:user_list'), c_dean)

        # Test Dept Chair
        self.client.force_login(self.chair)
        resp_chair = self.client.get(reverse('dashboard'))
        self.assertEqual(resp_chair.status_code, 200)
        c_chair = resp_chair.content.decode('utf-8')

        # Chair sees employee self-service links + staff operations
        self.assertIn(reverse('borrowing:my_borrowings'), c_chair)
        self.assertIn(reverse('assignments:my_accountability'), c_chair)
        self.assertIn(reverse('maintenance:my_reports'), c_chair)

        # Chair does NOT see custodian-only or admin-only links
        self.assertNotIn(reverse('student_reservations:custodian_list'), c_chair)
        self.assertNotIn(reverse('inventory:qr_labels_bulk'), c_chair)
        self.assertNotIn(reverse('audit:audit_log_list'), c_chair)
        self.assertNotIn(reverse('accounts:user_list'), c_chair)

    def test_operational_queue_action_buttons_per_role(self):
        """Custodians receive workflow actions ('Assess', 'Stock In', 'Review Disposals') while non-custodians receive read actions ('View Case', 'View Supply', 'View Disposals')."""
        # Create queue items
        maint = AssetMaintenance.objects.create(
            asset=self.asset,
            reported_by=self.chair,
            issue_title='Projector bulb failure',
            issue_description='Projector bulb burnt out',
            severity=AssetMaintenance.Severity.HIGH,
            status=AssetMaintenance.Status.REPORTED
        )
        scat = SupplyCategory.objects.create(name='Toner', code='TNR')
        supply = Supply.objects.create(
            item_name='Black Toner TN-100',
            supply_code='SUP-TNR-001',
            category=scat,
            reorder_level=5,
            unit=Supply.Unit.PIECE
        )
        SupplyTransaction.objects.create(
            supply=supply,
            transaction_type=SupplyTransaction.TransactionType.STOCK_IN,
            quantity=2,
            processed_by=self.admin
        )
        disposal = AssetDisposal.objects.create(
            asset=self.asset,
            reason='Obsolete hardware',
            disposal_method=AssetDisposal.DisposalMethod.SCRAP,
            status=AssetDisposal.Status.PENDING,
            requested_by=self.admin
        )

        # 1. Dean (read-only viewer)
        self.client.force_login(self.dean)
        resp_dean = self.client.get(reverse('dashboard'))
        self.assertEqual(resp_dean.status_code, 200)
        c_dean = resp_dean.content.decode('utf-8')

        self.assertIn('View Case', c_dean)
        self.assertIn('View Supply', c_dean)
        self.assertIn('View Disposals', c_dean)
        # Dean must not see administrative workflow buttons
        self.assertNotIn('>Assess<', c_dean.replace(' ', ''))
        self.assertNotIn('>Stock In<', c_dean.replace(' ', ''))
        self.assertNotIn('>Review Disposals<', c_dean.replace(' ', ''))

        # 2. Admin (custodian)
        self.client.force_login(self.admin)
        resp_admin = self.client.get(reverse('dashboard'))
        self.assertEqual(resp_admin.status_code, 200)
        c_admin = resp_admin.content.decode('utf-8')

        self.assertIn('Assess', c_admin)
        self.assertIn('Stock In', c_admin)
        self.assertIn('Review Disposals', c_admin)

    def test_dashboard_empty_state_zero_assets(self):
        """When 0 assets exist in database, all KPI values render 0 and charts display empty state placeholders."""
        Asset.objects.all().delete()
        self.client.force_login(self.admin)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # KPI counts render 0
        self.assertEqual(response.context['total_assets'], 0)
        self.assertEqual(response.context['available_assets'], 0)

        # Charts render graceful empty state text
        self.assertIn('No asset records in scope', content)
        self.assertIn('No category records in scope', content)
        self.assertIn('No distribution records in scope', content)

    def test_dashboard_header_actions_per_role(self):
        """Header displays Quick Actions / Management Tools for Admin and personal tools for Faculty."""
        # Admin header
        self.client.force_login(self.admin)
        resp_admin = self.client.get(reverse('dashboard'))
        c_admin = resp_admin.content.decode('utf-8')
        self.assertIn('Scan Asset', c_admin)
        self.assertIn('Assign Asset', c_admin)
        self.assertIn('Management Tools', c_admin)
        self.assertIn(reverse('inventory:asset_create'), c_admin)

        # Faculty header
        self.client.force_login(self.faculty)
        resp_faculty = self.client.get(reverse('dashboard'))
        c_faculty = resp_faculty.content.decode('utf-8')
        self.assertIn('Scan Asset', c_faculty)
        self.assertIn('My Accountability', c_faculty)
        self.assertIn('My Loans', c_faculty)
        self.assertNotIn('Management Tools', c_faculty)
        self.assertNotIn(reverse('assignments:assign_create'), c_faculty)

    def test_http_status_codes_on_key_target_views_per_role(self):
        """Verify HTTP response status codes for key views across ADMIN, DEAN, DEPT_CHAIR, and FACULTY."""
        # 1. Custodian-only management view: Admin=200, Dean=403, Chair=403, Faculty=403
        url_custodian = reverse('student_reservations:custodian_list')
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(url_custodian).status_code, 200)
        self.client.force_login(self.dean)
        self.assertEqual(self.client.get(url_custodian).status_code, 403)
        self.client.force_login(self.chair)
        self.assertEqual(self.client.get(url_custodian).status_code, 403)
        self.client.force_login(self.faculty)
        self.assertEqual(self.client.get(url_custodian).status_code, 403)

        # 2. Admin-only views: Admin=200, Dean=403, Chair=403, Faculty=403
        for url_name in ['inventory:qr_labels_bulk', 'audit:audit_log_list', 'accounts:user_list']:
            url = reverse(url_name)
            self.client.force_login(self.admin)
            self.assertEqual(self.client.get(url).status_code, 200)
            self.client.force_login(self.dean)
            self.assertEqual(self.client.get(url).status_code, 403)
            self.client.force_login(self.chair)
            self.assertEqual(self.client.get(url).status_code, 403)
            self.client.force_login(self.faculty)
            self.assertEqual(self.client.get(url).status_code, 403)

        # 3. Staff non-faculty views: Admin=200, Dean=200, Chair=200; Faculty receives 403 or safe redirect (302)
        for url_name, expected_faculty_status in [
            ('inventory:asset_list', 403),
            ('reports:reports_dashboard', 403),
            ('supplies:supply_list', 302),
            ('borrowing:active_list', 302),
            ('maintenance:case_list', 302),
        ]:
            url = reverse(url_name)
            self.client.force_login(self.admin)
            self.assertEqual(self.client.get(url).status_code, 200)
            self.client.force_login(self.dean)
            self.assertEqual(self.client.get(url).status_code, 200)
            self.client.force_login(self.chair)
            self.assertEqual(self.client.get(url).status_code, 200)
            self.client.force_login(self.faculty)
            self.assertEqual(self.client.get(url).status_code, expected_faculty_status)

        # 4. Universal authenticated views: 200 for all roles
        for url_name in ['dashboard', 'inventory:asset_scan']:
            url = reverse(url_name)
            for user in [self.admin, self.dean, self.chair, self.faculty]:
                self.client.force_login(user)
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_faculty_dashboard_hides_audit_supplies_categories_and_routes_personal_links(self):
        """Faculty dashboard omits global audit logs, supply reports, and category admin links, and routes loan queues to personal borrowings."""
        from apps.audit.models import AuditLog

        # Create global audit entry and low-stock supply
        AuditLog.objects.create(
            user=self.admin,
            action='ASSET_CREATED',
            model_name='Asset',
            object_id=str(self.asset.pk),
            object_repr='CBA-SECRET-AUDIT-999'
        )
        scat = SupplyCategory.objects.create(name='Paper', code='PPR2')
        Supply.objects.create(
            item_name='Restricted Supply Paper',
            supply_code='SUP-RES-001',
            category=scat,
            reorder_level=10,
            unit=Supply.Unit.REAM
        )

        # Create overdue and pending borrowings for Faculty
        AssetBorrowing.objects.create(
            asset=self.asset,
            borrower=self.emp_fac,
            borrower_department=self.dept,
            purpose='Faculty Overdue Loan',
            requested_start=self.now - timezone.timedelta(hours=5),
            requested_return=self.now - timezone.timedelta(hours=1),
            status=AssetBorrowing.Status.RELEASED,
            released_by=self.admin
        )
        asset_2 = Asset.objects.create(
            item_name='Second Faculty Laptop',
            asset_code='CBA-IT-00100',
            category=self.cat,
            department=self.dept,
            current_location=self.loc,
            condition=Asset.Condition.GOOD,
            status=Asset.Status.AVAILABLE
        )
        AssetBorrowing.objects.create(
            asset=asset_2,
            borrower=self.emp_fac,
            borrower_department=self.dept,
            purpose='Faculty Pending Loan',
            requested_start=self.now + timezone.timedelta(hours=2),
            requested_return=self.now + timezone.timedelta(hours=6),
            status=AssetBorrowing.Status.PENDING
        )

        self.client.force_login(self.faculty)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # 1. Global audit records and audit links are NOT exposed to Faculty
        self.assertNotIn('CBA-SECRET-AUDIT-999', content)
        self.assertNotIn('Recent System Activity', content)
        self.assertNotIn(reverse('audit:audit_log_list'), content)

        # 2. Restricted supply alerts, supply reports, and inventory category admin links are NOT shown to Faculty
        self.assertNotIn('Restricted Supply Paper', content)
        self.assertNotIn('Consumables &amp; Supplies', content)
        self.assertNotIn(reverse('reports:supplies_low_stock'), content)
        self.assertNotIn(reverse('supplies:low_stock_list'), content)
        self.assertNotIn(reverse('inventory:category_list'), content)

        # 3. Overdue and pending borrowing links route Faculty to permitted personal borrowing page
        self.assertIn(reverse('borrowing:my_borrowings'), content)
        self.assertIn('View My Loans', content)
        self.assertNotIn(f'href="{reverse("borrowing:active_list")}"', content)
        self.assertNotIn(f'href="{reverse("borrowing:request_list")}"', content)
        self.assertNotIn(f'href="{reverse("borrowing:request_list")}?status=PENDING"', content)

        # 4. Verify all personal links rendered for Faculty return 200 OK
        for permitted_url in [
            reverse('borrowing:my_borrowings'),
            reverse('assignments:my_accountability'),
            reverse('maintenance:my_reports'),
            reverse('inventory:asset_scan'),
        ]:
            self.assertEqual(self.client.get(permitted_url).status_code, 200)

    def test_damaged_assets_kpi_filter_link_and_inventory_filtering(self):
        """Damaged Assets KPI card links to ?status=DAMAGED and filters AssetListView accurately."""
        damaged_asset = Asset.objects.create(
            item_name='Damaged Audio Mixer',
            asset_code='CBA-IT-00101',
            category=self.cat,
            department=self.dept,
            current_location=self.loc,
            condition=Asset.Condition.POOR,
            status=Asset.Status.DAMAGED
        )

        expected_filter_url = f"{reverse('inventory:asset_list')}?status=DAMAGED"
        legacy_broken_url = f"{reverse('inventory:asset_list')}?condition=DAMAGED"

        for staff_user in [self.admin, self.dean, self.chair]:
            self.client.force_login(staff_user)
            dash_resp = self.client.get(reverse('dashboard'))
            self.assertEqual(dash_resp.status_code, 200)
            dash_html = dash_resp.content.decode('utf-8')

            self.assertIn(expected_filter_url, dash_html)
            self.assertNotIn(legacy_broken_url, dash_html)

            # Follow the Damaged KPI filter link and verify it returns only damaged assets
            list_resp = self.client.get(expected_filter_url)
            self.assertEqual(list_resp.status_code, 200)
            list_html = list_resp.content.decode('utf-8')
            self.assertIn(damaged_asset.item_name, list_html)
            self.assertNotIn(self.asset.item_name, list_html)
