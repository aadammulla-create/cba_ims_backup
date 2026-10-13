from datetime import timedelta
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.forms import LoginForm
from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.inventory.models import Asset, AssetCategory
from apps.organizations.models import Department
from apps.student_reservations.models import StudentReservation


class Phase3CPublicLandingAndLoginTests(TestCase):
    """Focused Phase 3C verification tests for the public landing page,
    staff login redesign, routing/redirect rules, and public/private boundaries.
    """

    @classmethod
    def setUpTestData(cls):
        cls.password = 'Phase3CTestPass!2026'
        cls.admin_user = User.objects.create_user(
            username='phase3c_admin',
            email='phase3c_admin@cba.edu',
            password=cls.password,
            first_name='System',
            last_name='Custodian',
            role=User.Role.ADMIN,
        )
        cls.faculty_user = User.objects.create_user(
            username='phase3c_faculty',
            email='phase3c_faculty@cba.edu',
            password=cls.password,
            first_name='Elena',
            last_name='Reyes',
            role=User.Role.FACULTY,
        )

        # Seed private operational records to verify they are never leaked on '/'
        cls.dept = Department.objects.create(name='Accountancy', code='ACCT3C')
        cls.category = AssetCategory.objects.create(name='IT Equipment 3C', code='IT3C')
        cls.private_asset = Asset.objects.create(
            asset_code='CBA-SECRET-9901',
            item_name='Confidential Server Rack Alpha',
            serial_number='SN-PRIVATE-88219',
            category=cls.category,
            department=cls.dept,
            status=Asset.Status.AVAILABLE,
        )
        cls.private_reservation = StudentReservation.objects.create(
            student_name='Juan Dela Cruz PrivatePII',
            student_id='2026-998877',
            email='juandelacruz.secret@student.cba.edu',
            contact_number='09179998877',
            course_year_section='BSBA-4A',
            category=cls.category,
            equipment_type='Projector',
            purpose='Confidential Thesis Defense',
            room_venue='CBA-402',
            requested_pickup=timezone.now() + timedelta(days=1),
            requested_return=timezone.now() + timedelta(days=1, hours=2),
        )
        cls.private_audit = AuditLog.objects.create(
            user=cls.admin_user,
            action='CREATE',
            model_name='Asset',
            object_id=str(cls.private_asset.id),
            object_repr='CBA-SECRET-9901 Confidential Audit Entry',
            changes={'note': 'Internal custodian audit trail entry'},
        )

    # ------------------------------------------------------------------
    # 1. Public Landing Page & Primary Actions
    # ------------------------------------------------------------------

    def test_anonymous_root_returns_public_landing_page_http_200(self):
        """Anonymous GET / serves the public landing page (HTTP 200) without redirecting."""
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/landing.html')
        self.assertContains(response, 'CBA IMS')
        self.assertContains(response, 'College of Business Administration')
        self.assertContains(response, 'Student Reservation Process Overview')
        self.assertContains(response, 'Public Student Services')
        self.assertContains(response, 'Authenticated Staff Operations')

    def test_public_landing_page_includes_primary_action_links_for_anonymous_visitor(self):
        """Public homepage exposes Browse Equipment, Track Reservation, Reserve, and Staff Sign In."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

        catalog_url = reverse('student_reservations:catalog')
        request_url = reverse('student_reservations:public_request')
        lookup_url = reverse('student_reservations:public_lookup_search')
        login_url = reverse('accounts:login')

        self.assertContains(response, 'Browse Equipment')
        self.assertContains(response, 'Track Reservation')
        self.assertContains(response, 'Staff Sign In')
        self.assertContains(response, f'href="{catalog_url}"')
        self.assertContains(response, f'href="{request_url}"')
        self.assertContains(response, f'href="{lookup_url}"')
        self.assertContains(response, f'href="{login_url}"')

    def test_public_landing_page_does_not_expose_private_records_or_pii(self):
        """Public homepage must never expose private inventory items, student PII, or audit logs."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')

        self.assertNotIn('CBA-SECRET-9901', html)
        self.assertNotIn('Confidential Server Rack Alpha', html)
        self.assertNotIn('SN-PRIVATE-88219', html)
        self.assertNotIn('Juan Dela Cruz PrivatePII', html)
        self.assertNotIn('2026-998877', html)
        self.assertNotIn('juandelacruz.secret@student.cba.edu', html)
        self.assertNotIn(self.private_reservation.lookup_token, html)
        self.assertNotIn('Confidential Audit Entry', html)
        self.assertNotIn('Internal custodian audit trail entry', html)

    # ------------------------------------------------------------------
    # 2. Anonymous vs. Authenticated Routing & Dashboard Access
    # ------------------------------------------------------------------

    def test_anonymous_dashboard_redirects_to_staff_login_with_next(self):
        """Anonymous GET /dashboard/ redirects to /accounts/login/?next=/dashboard/."""
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/accounts/login/?next=/dashboard/')

    def test_authenticated_user_visiting_root_sees_go_to_dashboard_action(self):
        """Authenticated users visiting GET / receive HTTP 200 with a clear Go to Dashboard action."""
        self.client.force_login(self.faculty_user)
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/landing.html')
        self.assertContains(response, 'Go to Dashboard')
        self.assertContains(response, f'href="{reverse("dashboard")}"')

    def test_authenticated_user_visiting_login_redirects_to_dashboard(self):
        """Authenticated users visiting GET /accounts/login/ are redirected to /dashboard/."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('accounts:login'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('dashboard'))

    def test_authenticated_user_can_access_dashboard(self):
        """Authenticated staff users can access GET /dashboard/ (HTTP 200)."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/dashboard.html')

    # ------------------------------------------------------------------
    # 3. Staff Login Redesign & Authentication Behavior
    # ------------------------------------------------------------------

    def test_staff_login_page_renders_institutional_layout_and_form(self):
        """GET /accounts/login/ renders Staff Sign In heading, LoginForm, CSRF token, and homepage link."""
        response = self.client.get(reverse('accounts:login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/login.html')
        self.assertIsInstance(response.context['form'], LoginForm)
        self.assertContains(response, 'Staff Sign In')
        self.assertContains(response, 'CBA IMS')
        self.assertContains(response, 'csrfmiddlewaretoken')
        self.assertContains(response, f'href="{reverse("home")}"')

    def test_successful_staff_login_redirects_to_dashboard_by_default(self):
        """Valid staff login POST without next parameter redirects to /dashboard/."""
        response = self.client.post(
            reverse('accounts:login'),
            {'username': self.admin_user.username, 'password': self.password},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('dashboard'))

    def test_failed_staff_login_displays_error_alert_and_stays_on_login(self):
        """Invalid credentials return HTTP 200 with clear error message and unauthenticated session."""
        response = self.client.post(
            reverse('accounts:login'),
            {'username': self.admin_user.username, 'password': 'WrongPassword!999'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/login.html')
        self.assertContains(response, 'Authentication failed')
        self.assertNotIn('_auth_user_id', self.client.session)

    # ------------------------------------------------------------------
    # 4. Safe Handling of `next` Redirects
    # ------------------------------------------------------------------

    def test_login_honors_valid_safe_internal_next_url(self):
        """Valid internal next URL is preserved in the login form and honored upon login."""
        safe_next = '/inventory/assets/'
        get_res = self.client.get(reverse('accounts:login'), {'next': safe_next})
        self.assertEqual(get_res.status_code, 200)
        self.assertContains(get_res, f'name="next" value="{safe_next}"')

        post_res = self.client.post(
            reverse('accounts:login'),
            {
                'username': self.admin_user.username,
                'password': self.password,
                'next': safe_next,
            },
        )
        self.assertEqual(post_res.status_code, 302)
        self.assertEqual(post_res['Location'], safe_next)

    def test_login_rejects_external_or_unsafe_next_urls(self):
        """External or protocol-relative next URLs are rejected and fall back to /dashboard/."""
        unsafe_targets = [
            'https://evil.example.com/phish',
            'http://attacker.invalid/login',
            '//evil.example.com/protocol-relative',
            'javascript:alert(1)',
        ]
        for unsafe_next in unsafe_targets:
            with self.subTest(unsafe_next=unsafe_next):
                self.client.logout()
                response = self.client.post(
                    f"{reverse('accounts:login')}?next={unsafe_next}",
                    {
                        'username': self.faculty_user.username,
                        'password': self.password,
                        'next': unsafe_next,
                    },
                )
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response['Location'], reverse('dashboard'))

    def test_authenticated_user_on_login_rejects_unsafe_next_url(self):
        """Authenticated user visiting /accounts/login/?next=//evil.example.com redirects safely to /dashboard/."""
        self.client.force_login(self.faculty_user)
        response = self.client.get(reverse('accounts:login'), {'next': '//evil.example.com/steal'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('dashboard'))

    # ------------------------------------------------------------------
    # 5. Existing Student Reservation Workflows Connected & Public
    # ------------------------------------------------------------------

    def test_existing_public_student_reservation_routes_remain_accessible_without_login(self):
        """Catalog, reservation request form, and reservation lookup remain accessible anonymously."""
        public_routes = [
            reverse('student_reservations:catalog'),
            reverse('student_reservations:public_request'),
            reverse('student_reservations:public_lookup_search'),
        ]
        for url in public_routes:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
