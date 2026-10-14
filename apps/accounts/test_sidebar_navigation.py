from django.test import TestCase, Client
from django.urls import reverse
from apps.accounts.models import User
from apps.organizations.models import Department, Location, Employee

class SidebarNavigationRBACTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.dept_ba = Department.objects.create(name='Department of Business Administration', code='BA')
        cls.dept_acct = Department.objects.create(name='Department of Accountancy', code='ACCT')
        
        cls.loc_main = Location.objects.create(
            name='CBA Main Office', building='Main', room_number='101', department=cls.dept_ba
        )
        
        # 1. Admin user
        cls.admin = User.objects.create_superuser(
            username='admin_nav_test',
            email='admin@cba.edu',
            password='Pass1234!',
            role=User.Role.ADMIN,
            first_name='Property',
            last_name='Custodian'
        )
        cls.admin_emp = Employee.objects.create(
            user=cls.admin,
            employee_id='EMP-ADM-TEST',
            first_name='Property',
            last_name='Custodian',
            department=cls.dept_ba,
            location=cls.loc_main
        )

        # 2. Dept Chair user
        cls.chair = User.objects.create_user(
            username='chair_nav_test',
            email='chair@cba.edu',
            password='Pass1234!',
            role=User.Role.DEPT_CHAIR,
            first_name='Elena',
            last_name='Santos'
        )
        cls.chair_emp = Employee.objects.create(
            user=cls.chair,
            employee_id='EMP-CHR-TEST',
            first_name='Elena',
            last_name='Santos',
            department=cls.dept_acct,
            location=cls.loc_main
        )

        # 3. Faculty user
        cls.faculty = User.objects.create_user(
            username='faculty_nav_test',
            email='faculty@cba.edu',
            password='Pass1234!',
            role=User.Role.FACULTY,
            first_name='Maria',
            last_name='Santos'
        )
        cls.faculty_emp = Employee.objects.create(
            user=cls.faculty,
            employee_id='EMP-FAC-TEST',
            first_name='Maria',
            last_name='Santos',
            department=cls.dept_acct,
            location=cls.loc_main
        )

    def setUp(self):
        self.client = Client(SERVER_NAME='127.0.0.1')

    def test_admin_sidebar_has_authorized_links_and_no_duplicates(self):
        """Verify Admin role gets all 6 primary queues and full administrative secondary groups."""
        self.client.force_login(self.admin)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Primary Links (6 links)
        self.assertIn(reverse('dashboard'), content)
        self.assertIn(reverse('inventory:asset_list'), content)
        self.assertIn(reverse('student_reservations:custodian_list'), content)
        self.assertIn(reverse('borrowing:active_list'), content)
        self.assertIn(reverse('maintenance:case_list'), content)
        self.assertIn(reverse('reports:reports_dashboard'), content)

        # Secondary Links
        self.assertIn(reverse('inventory:asset_scan'), content)
        self.assertIn(reverse('inventory:category_list'), content)
        self.assertIn(reverse('inventory:physical_verification_list'), content)
        self.assertIn(reverse('organizations:location_list'), content)
        self.assertIn(reverse('inventory:qr_labels_bulk'), content)
        self.assertIn(reverse('assignments:current_list'), content)
        self.assertIn(reverse('transfers:pending_list'), content)
        self.assertIn(reverse('disposals:pending_list'), content)
        self.assertIn(reverse('maintenance:report_create'), content)
        self.assertIn(reverse('supplies:supply_list'), content)
        self.assertIn(reverse('supplies:transaction_list'), content)
        self.assertIn(reverse('supplies:low_stock_list'), content)
        self.assertIn(reverse('organizations:employee_list'), content)
        self.assertIn(reverse('organizations:department_list'), content)
        self.assertIn(reverse('accounts:user_list'), content)
        self.assertIn(reverse('audit:audit_log_list'), content)

        # Verify no duplicate primary links in secondary groups
        # Note: sidebar_nav is rendered once in #desktop-sidebar and once in #sidebarMenu (mobile offcanvas).
        desktop_start = content.find('id="desktop-sidebar"')
        desktop_end = content.find('</nav>', desktop_start)
        desktop_sidebar = content[desktop_start:desktop_end] if desktop_start != -1 else content

        self.assertEqual(desktop_sidebar.count(f'href="{reverse("inventory:asset_list")}"'), 1)
        self.assertEqual(desktop_sidebar.count(f'href="{reverse("borrowing:active_list")}"'), 1)
        self.assertEqual(desktop_sidebar.count(f'href="{reverse("maintenance:case_list")}"'), 1)
        self.assertEqual(desktop_sidebar.count(f'href="{reverse("reports:reports_dashboard")}"'), 1)

    def test_dept_chair_sidebar_has_scoped_access_and_no_unauthorized_destinations(self):
        """Verify Department Chair sees only department-relevant links and zero admin-only controls."""
        self.client.force_login(self.chair)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        sidebar_start = content.find('class="sidebar-nav"')
        sidebar_end = content.find('<!-- Main Content Area -->')
        sidebar_content = content[sidebar_start:sidebar_end] if sidebar_start != -1 else content

        # Primary Links (5 links: Dashboard, Asset Register, Borrowing, Maintenance, Reports)
        self.assertIn(f'href="{reverse("dashboard")}"', sidebar_content)
        self.assertIn(f'href="{reverse("inventory:asset_list")}"', sidebar_content)
        self.assertIn(f'href="{reverse("borrowing:active_list")}"', sidebar_content)
        self.assertIn(f'href="{reverse("maintenance:case_list")}"', sidebar_content)
        self.assertIn(f'href="{reverse("reports:reports_dashboard")}"', sidebar_content)

        # Authorized Secondary Links
        self.assertIn(f'href="{reverse("inventory:asset_scan")}"', sidebar_content)
        self.assertIn(f'href="{reverse("inventory:category_list")}"', sidebar_content)
        self.assertIn(f'href="{reverse("inventory:physical_verification_list")}"', sidebar_content)
        self.assertIn(f'href="{reverse("organizations:location_list")}"', sidebar_content)
        self.assertIn(f'href="{reverse("assignments:current_list")}"', sidebar_content)
        self.assertIn(f'href="{reverse("transfers:pending_list")}"', sidebar_content)
        self.assertIn(f'href="{reverse("disposals:pending_list")}"', sidebar_content)
        self.assertIn(f'href="{reverse("supplies:supply_list")}"', sidebar_content)
        self.assertIn(f'href="{reverse("organizations:employee_list")}"', sidebar_content)
        self.assertIn(f'href="{reverse("organizations:department_list")}"', sidebar_content)

        # STRICT RBAC: Unauthorized admin-only destinations MUST NOT appear
        self.assertNotIn(f'href="{reverse("student_reservations:custodian_list")}"', sidebar_content)
        self.assertNotIn(f'href="{reverse("inventory:qr_labels_bulk")}"', sidebar_content)
        self.assertNotIn(f'href="{reverse("accounts:user_list")}"', sidebar_content)
        self.assertNotIn(f'href="{reverse("audit:audit_log_list")}"', sidebar_content)

    def test_faculty_sidebar_prioritizes_self_service_and_hides_admin_queues(self):
        """Verify Faculty sees prioritized self-service links and zero management/admin queues."""
        self.client.force_login(self.faculty)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        sidebar_start = content.find('class="sidebar-nav"')
        sidebar_end = content.find('<!-- Main Content Area -->')
        sidebar_content = content[sidebar_start:sidebar_end] if sidebar_start != -1 else content

        # Primary Self-Service Links (6 links)
        self.assertIn(f'href="{reverse("dashboard")}"', sidebar_content)
        self.assertIn(f'href="{reverse("assignments:my_accountability")}"', sidebar_content)
        self.assertIn(f'href="{reverse("borrowing:my_borrowings")}"', sidebar_content)
        self.assertIn(f'href="{reverse("borrowing:request_create")}"', sidebar_content)
        self.assertIn(f'href="{reverse("maintenance:my_reports")}"', sidebar_content)
        self.assertIn(f'href="{reverse("maintenance:report_create")}"', sidebar_content)

        # Authorized Secondary Links
        self.assertIn(f'href="{reverse("inventory:asset_scan")}"', sidebar_content)
        self.assertIn(f'href="{reverse("organizations:location_list")}"', sidebar_content)
        self.assertIn(f'href="{reverse("organizations:employee_list")}"', sidebar_content)
        self.assertIn(f'href="{reverse("organizations:department_list")}"', sidebar_content)

        # STRICT RBAC: Faculty must NOT see any staff queues, supplies, or admin features in sidebar
        self.assertNotIn(f'href="{reverse("inventory:asset_list")}"', sidebar_content)
        self.assertNotIn(f'href="{reverse("student_reservations:custodian_list")}"', sidebar_content)
        self.assertNotIn(f'href="{reverse("borrowing:active_list")}"', sidebar_content)
        self.assertNotIn(f'href="{reverse("maintenance:case_list")}"', sidebar_content)
        self.assertNotIn(f'href="{reverse("reports:reports_dashboard")}"', sidebar_content)
        self.assertNotIn(f'href="{reverse("inventory:category_list")}"', sidebar_content)
        self.assertNotIn(f'href="{reverse("inventory:physical_verification_list")}"', sidebar_content)
        self.assertNotIn(f'href="{reverse("inventory:qr_labels_bulk")}"', sidebar_content)
        self.assertNotIn(f'href="{reverse("assignments:current_list")}"', sidebar_content)
        self.assertNotIn(f'href="{reverse("transfers:pending_list")}"', sidebar_content)
        self.assertNotIn(f'href="{reverse("disposals:pending_list")}"', sidebar_content)
        self.assertNotIn(f'href="{reverse("supplies:supply_list")}"', sidebar_content)
        self.assertNotIn(f'href="{reverse("supplies:transaction_list")}"', sidebar_content)
        self.assertNotIn(f'href="{reverse("supplies:low_stock_list")}"', sidebar_content)
        self.assertNotIn(f'href="{reverse("accounts:user_list")}"', sidebar_content)
        self.assertNotIn(f'href="{reverse("audit:audit_log_list")}"', sidebar_content)

    def test_active_highlighting_and_group_expansion(self):
        """Verify active page has 'active' class and parent collapsible group renders 'open'."""
        self.client.force_login(self.admin)
        
        # 1. On Dashboard: dashboard link is active, secondary groups closed
        resp_dash = self.client.get(reverse('dashboard'))
        content_dash = resp_dash.content.decode('utf-8')
        self.assertIn(f'href="{reverse("dashboard")}" class="nav-link active"', content_dash)
        
        # 2. On Supplies list: supplies group has 'open' attribute and supply_list link is active
        resp_supplies = self.client.get(reverse('supplies:supply_list'))
        self.assertEqual(resp_supplies.status_code, 200)
        content_supplies = resp_supplies.content.decode('utf-8')
        
        self.assertIn(f'href="{reverse("supplies:supply_list")}" class="nav-link active"', content_supplies)
        # Verify the details element for supplies is open
        self.assertIn('<details class="sidebar-group" open>', content_supplies)

    def test_faculty_active_highlighting_on_accountability(self):
        """Verify Faculty on My Accountability page has active highlighting."""
        self.client.force_login(self.faculty)
        resp = self.client.get(reverse('assignments:my_accountability'))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn(f'href="{reverse("assignments:my_accountability")}" class="nav-link active"', content)
