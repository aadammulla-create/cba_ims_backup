from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from apps.inventory.models import AssetCategory, EquipmentType, Brand, Asset
from apps.organizations.models import Department, Location
from apps.student_reservations.models import StudentReservation

User = get_user_model()


class StaffCustodianQueueMobileUXTests(TestCase):
    """
    Focused tests for Phase 4D2 Staff Custodian Queue Mobile UX:
    1. Empty-state rendering (unfiltered vs filtered) outside of table containers.
    2. Populated queue dual rendering (desktop operational table + mobile card stack).
    3. Mobile reservation card contents and touch-friendly Manage links.
    4. Status tab filtering and search parameter persistence.
    5. Staff RBAC authorization boundaries (Admin vs Faculty vs Anonymous).
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

        # Category, Brand, Equipment Type, Asset
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
        self.asset = Asset.objects.create(
            asset_code='PRJ-TEST-001',
            item_name='Epson EB-X06',
            category=self.cat_proj,
            equipment_type=self.eq_type,
            brand=self.brand,
            department=self.dept,
            current_location=self.loc,
            status=Asset.Status.AVAILABLE,
            condition=Asset.Condition.GOOD,
            is_reservable=True
        )

        now = timezone.localtime()
        self.pickup_dt = now + timedelta(days=1, hours=1)
        self.return_dt = self.pickup_dt + timedelta(hours=3)

    def test_empty_queue_unfiltered_renders_dedicated_empty_state_without_table(self):
        """When queue has no reservations, renders full-viewport empty state without <table>."""
        self.client.force_login(self.admin_user)
        url = reverse('student_reservations:custodian_list')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

        content = resp.content.decode()
        # Verify empty state guidance
        self.assertIn("Queue is empty", content)
        self.assertIn("There are currently no active student equipment reservations", content)
        self.assertIn("View Catalog", content)
        self.assertIn("Submit Test Request", content)

        # Verify no 7-column table is rendered to prevent mobile table overflow
        self.assertNotIn("<table", content)
        self.assertNotIn("No student reservations found matching this criteria", content)

    def test_empty_queue_filtered_renders_filtered_guidance_and_clear_button(self):
        """When filter yields no results, renders helpful filter-aware empty card with clear link."""
        self.client.force_login(self.admin_user)
        url = reverse('student_reservations:custodian_list')
        resp = self.client.get(url, {'status': 'PENDING', 'q': 'NonexistentQuery'})
        self.assertEqual(resp.status_code, 200)

        content = resp.content.decode()
        self.assertIn("No reservations found", content)
        self.assertIn("PENDING", content)
        self.assertIn("NonexistentQuery", content)
        self.assertIn("Clear Filters", content)
        self.assertIn(reverse('student_reservations:custodian_list'), content)
        self.assertNotIn("<table", content)

    def test_populated_queue_renders_both_desktop_table_and_mobile_cards(self):
        """Populated queue renders responsive desktop table (d-none d-md-block) and mobile cards (d-md-none)."""
        res = StudentReservation.objects.create(
            student_id='2024-00101',
            student_name='Maria Clara Santos',
            email='mclara@cba.edu',
            contact_number='09171234567',
            course_year_section='BSBA 3-A',
            category=self.cat_proj,
            equipment_type_ref=self.eq_type,
            requested_pickup=self.pickup_dt,
            requested_return=self.return_dt,
            purpose='Strategic Management Lecture',
            status=StudentReservation.Status.PENDING
        )

        self.client.force_login(self.admin_user)
        url = reverse('student_reservations:custodian_list')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

        content = resp.content.decode()

        # Both desktop table and mobile card stack exist
        self.assertIn("d-none d-md-block", content)
        self.assertIn("d-md-none", content)

        # Desktop table structure
        self.assertIn("<table class=\"table table-hover align-middle mb-0\">", content)
        self.assertIn("Student Requester", content)
        self.assertIn("Allocated Asset", content)

        # Mobile card contents
        self.assertIn("Maria Clara Santos", content)
        self.assertIn("2024-00101", content)
        self.assertIn("BSBA 3-A", content)
        self.assertIn("Strategic Management Lecture", content)
        self.assertIn("Classroom LCD Projector", content)
        self.assertIn("Manage Reservation", content)
        # Privacy: Lookup tokens must not be exposed in queue markup
        self.assertNotIn("Ref: ", content)
        self.assertNotIn(res.lookup_token, content)

        # Verify manage URL link
        manage_url = reverse('student_reservations:custodian_detail', kwargs={'pk': res.pk})
        self.assertIn(manage_url, content)

    def test_status_filters_and_search_query_execution(self):
        """Status filters and search queries correctly isolate matching reservations."""
        res_pending = StudentReservation.objects.create(
            student_id='2024-00201',
            student_name='Jose Rizal',
            email='jrizal@cba.edu',
            contact_number='09171234568',
            category=self.cat_proj,
            requested_pickup=self.pickup_dt,
            requested_return=self.return_dt,
            purpose='History Report',
            status=StudentReservation.Status.PENDING
        )
        res_released = StudentReservation.objects.create(
            student_id='2024-00202',
            student_name='Andres Bonifacio',
            email='abonifacio@cba.edu',
            contact_number='09171234569',
            category=self.cat_proj,
            asset=self.asset,
            requested_pickup=self.pickup_dt,
            requested_return=self.return_dt,
            purpose='General Assembly',
            status=StudentReservation.Status.RELEASED
        )

        self.client.force_login(self.admin_user)
        url = reverse('student_reservations:custodian_list')

        # Filter by PENDING
        resp_pending = self.client.get(url, {'status': 'PENDING'})
        self.assertEqual(resp_pending.status_code, 200)
        self.assertContains(resp_pending, 'Jose Rizal')
        self.assertNotContains(resp_pending, 'Andres Bonifacio')

        # Filter by RELEASED
        resp_released = self.client.get(url, {'status': 'RELEASED'})
        self.assertEqual(resp_released.status_code, 200)
        self.assertContains(resp_released, 'Andres Bonifacio')
        self.assertNotContains(resp_released, 'Jose Rizal')

        # Search by student ID
        resp_search = self.client.get(url, {'q': '2024-00201'})
        self.assertEqual(resp_search.status_code, 200)
        self.assertContains(resp_search, 'Jose Rizal')
        self.assertNotContains(resp_search, 'Andres Bonifacio')

    def test_rbac_authorization_boundaries_for_custodian_queue(self):
        """Verify strict RBAC: Admin=200, Faculty=403, Anonymous=302."""
        url = reverse('student_reservations:custodian_list')

        # 1. Anonymous -> 302 Redirect to staff login
        resp_anon = self.client.get(url)
        self.assertEqual(resp_anon.status_code, 302)
        self.assertIn('/accounts/login/', resp_anon.url)

        # 2. Faculty -> 403 Forbidden
        self.client.force_login(self.faculty_user)
        resp_fac = self.client.get(url)
        self.assertEqual(resp_fac.status_code, 403)

        # 3. Admin -> 200 OK
        self.client.force_login(self.admin_user)
        resp_admin = self.client.get(url)
        self.assertEqual(resp_admin.status_code, 200)
        self.assertTemplateUsed(resp_admin, 'student_reservations/custodian_list.html')
