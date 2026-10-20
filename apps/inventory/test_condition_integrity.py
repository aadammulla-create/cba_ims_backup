from decimal import Decimal
from datetime import timedelta
from django.test import TestCase, RequestFactory
from django.contrib.admin.sites import AdminSite
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.accounts.models import User
from apps.organizations.models import Department, Location, Employee
from apps.inventory.models import Asset, AssetCategory, Brand
from apps.inventory.forms import AssetForm, AssetUpdateForm
from apps.inventory.views import AssetUpdateView
from apps.inventory.admin import AssetAdmin
from apps.assignments import services as assignment_services
from apps.assignments.forms import AssetAssignmentForm
from apps.borrowing import services as borrowing_services
from apps.borrowing.models import AssetBorrowing
from apps.student_reservations import services as student_res_services
from apps.student_reservations.models import StudentReservation


class MockSuperUser:
    def has_perm(self, perm):
        return True


class AssetConditionIntegrityTests(TestCase):
    """
    Comprehensive test suite verifying Phase 3A Asset Condition Integrity Hardening:
    1. AssetUpdateForm excludes condition; AssetForm preserves condition.
    2. AssetUpdateView locks condition to old_instance.condition.
    3. AssetAdmin read-only condition on change and preservation on save_model.
    4. assign_asset() rejects UNSERVICEABLE assets.
    5. AssetAssignmentForm queryset excludes UNSERVICEABLE assets.
    6. request_borrowing() and release_asset() reject UNSERVICEABLE assets.
    7. get_reservable_assets(), check_asset_availability(), and release_equipment() reject UNSERVICEABLE assets.
    """

    def setUp(self):
        self.factory = RequestFactory()
        self.site = AdminSite()

        self.admin = User.objects.create_user(
            username='admin_cond',
            email='admin_cond@cba.edu',
            password='Password123!',
            role=User.Role.ADMIN
        )
        self.faculty = User.objects.create_user(
            username='faculty_cond',
            email='faculty_cond@cba.edu',
            password='Password123!',
            role=User.Role.FACULTY
        )

        self.dept = Department.objects.create(name='Accountancy', code='ACC')
        self.loc = Location.objects.create(name='ACC Lab', department=self.dept)
        self.emp = Employee.objects.create(
            user=self.faculty,
            employee_id='EMP-ACC-01',
            first_name='Juan',
            last_name='Luna',
            department=self.dept,
            location=self.loc
        )

        self.cat = AssetCategory.objects.create(
            name='Computer Equipment',
            code='CMP',
            is_active=True,
            is_reservable=True
        )
        self.brand = Brand.objects.create(name='Lenovo', is_active=True)

        self.serviceable_asset = Asset.objects.create(
            item_name='ThinkPad T14',
            category=self.cat,
            brand=self.brand,
            department=self.dept,
            current_location=self.loc,
            condition=Asset.Condition.GOOD,
            status=Asset.Status.AVAILABLE,
            acquisition_cost=Decimal('50000.00'),
            created_by=self.admin
        )

        self.unserviceable_asset = Asset.objects.create(
            item_name='Broken Projector',
            category=self.cat,
            brand=self.brand,
            department=self.dept,
            current_location=self.loc,
            condition=Asset.Condition.UNSERVICEABLE,
            status=Asset.Status.AVAILABLE,
            acquisition_cost=Decimal('35000.00'),
            created_by=self.admin
        )

        self.now = timezone.now()

    # --------------------------------------------------------------------------
    # 1. Forms: condition excluded from AssetUpdateForm, preserved in AssetForm
    # --------------------------------------------------------------------------
    def test_asset_update_form_excludes_condition_field(self):
        form = AssetUpdateForm(instance=self.serviceable_asset)
        self.assertNotIn('condition', form.fields)
        expected_fields = [
            'item_name', 'category', 'brand', 'model', 'description',
            'property_number', 'serial_number', 'acquisition_date',
            'acquisition_cost', 'supplier', 'remarks', 'asset_image'
        ]
        self.assertEqual(list(form.fields.keys()), expected_fields)

    def test_asset_create_form_preserves_condition_field(self):
        form = AssetForm()
        self.assertIn('condition', form.fields)

    # --------------------------------------------------------------------------
    # 2. Views: AssetUpdateView server-side lock on condition
    # --------------------------------------------------------------------------
    def test_asset_update_view_locks_condition(self):
        from django.urls import reverse
        self.client.login(username='admin_cond', password='Password123!')
        url = reverse('inventory:asset_edit', kwargs={'asset_code': self.serviceable_asset.asset_code})

        post_data = {
            'item_name': 'ThinkPad T14 (Renamed)',
            'category': self.cat.pk,
            'brand': self.brand.pk,
            'model': 'T14 Gen 2',
            'acquisition_cost': '52000.00',
            'condition': Asset.Condition.POOR,
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302)

        self.serviceable_asset.refresh_from_db()
        self.assertEqual(self.serviceable_asset.item_name, 'ThinkPad T14 (Renamed)')
        self.assertEqual(self.serviceable_asset.condition, Asset.Condition.GOOD)

    # --------------------------------------------------------------------------
    # 3. Admin: AssetAdmin readonly condition & save_model restoration
    # --------------------------------------------------------------------------
    def test_asset_admin_readonly_fields_behavior(self):
        admin = AssetAdmin(Asset, self.site)
        request = self.factory.get('/admin/inventory/asset/add/')
        request.user = self.admin

        # Creating new asset: condition must NOT be read-only
        readonly_add = admin.get_readonly_fields(request, obj=None)
        self.assertNotIn('condition', readonly_add)

        # Modifying existing asset: condition MUST be read-only
        readonly_change = admin.get_readonly_fields(request, obj=self.serviceable_asset)
        self.assertIn('condition', readonly_change)
        self.assertIn('status', readonly_change)
        self.assertIn('department', readonly_change)
        self.assertIn('current_location', readonly_change)

    def test_asset_admin_save_model_restores_condition_on_change(self):
        admin = AssetAdmin(Asset, self.site)
        request = self.factory.post('/admin/inventory/asset/')
        request.user = self.admin

        # Simulate forged change in admin
        target_asset = Asset.objects.get(pk=self.serviceable_asset.pk)
        target_asset.condition = Asset.Condition.UNSERVICEABLE
        target_asset.status = Asset.Status.DISPOSED

        admin.save_model(request, target_asset, form=None, change=True)
        target_asset.refresh_from_db()

        # Both condition and status must be restored to original values
        self.assertEqual(target_asset.condition, Asset.Condition.GOOD)
        self.assertEqual(target_asset.status, Asset.Status.AVAILABLE)

    # --------------------------------------------------------------------------
    # 4. Assignments: assign_asset() rejects UNSERVICEABLE assets
    # --------------------------------------------------------------------------
    def test_assign_asset_rejects_unserviceable_asset(self):
        with self.assertRaises(ValidationError) as ctx:
            assignment_services.assign_asset(
                asset=self.unserviceable_asset,
                employee=self.emp,
                assigned_by=self.admin,
                purpose="Classroom delivery"
            )
        self.assertIn("cannot be assigned because its condition is UNSERVICEABLE", str(ctx.exception))

    def test_assign_asset_succeeds_for_serviceable_asset(self):
        assignment = assignment_services.assign_asset(
            asset=self.serviceable_asset,
            employee=self.emp,
            assigned_by=self.admin,
            purpose="Classroom delivery"
        )
        self.assertIsNotNone(assignment)
        self.serviceable_asset.refresh_from_db()
        self.assertEqual(self.serviceable_asset.status, Asset.Status.ASSIGNED)

    # --------------------------------------------------------------------------
    # 5. Assignments Form: AssetAssignmentForm excludes UNSERVICEABLE assets
    # --------------------------------------------------------------------------
    def test_asset_assignment_form_queryset_excludes_unserviceable(self):
        form = AssetAssignmentForm()
        qs = form.fields['asset'].queryset
        self.assertIn(self.serviceable_asset, qs)
        self.assertNotIn(self.unserviceable_asset, qs)

    # --------------------------------------------------------------------------
    # 6. Borrowing: request_borrowing() and release_asset() condition validation
    # --------------------------------------------------------------------------
    def test_request_borrowing_rejects_unserviceable_asset(self):
        with self.assertRaises(ValidationError) as ctx:
            borrowing_services.request_borrowing(
                asset=self.unserviceable_asset,
                borrower=self.emp,
                purpose="Faculty research",
                requested_start=self.now + timedelta(hours=1),
                requested_return=self.now + timedelta(hours=3),
                created_by=self.faculty
            )
        self.assertIn("cannot be borrowed because its condition is UNSERVICEABLE", str(ctx.exception))

    def test_release_asset_rejects_unserviceable_asset_or_condition(self):
        borrowing = borrowing_services.request_borrowing(
            asset=self.serviceable_asset,
            borrower=self.emp,
            purpose="Faculty research",
            requested_start=self.now + timedelta(hours=1),
            requested_return=self.now + timedelta(hours=3),
            created_by=self.faculty
        )
        borrowing_services.approve_borrowing(borrowing, reviewed_by=self.admin)

        # 6a. Attempt to release with condition_at_release=UNSERVICEABLE
        with self.assertRaises(ValidationError) as ctx:
            borrowing_services.release_asset(
                borrowing=borrowing,
                released_by=self.admin,
                condition_at_release=Asset.Condition.UNSERVICEABLE
            )
        self.assertIn("in UNSERVICEABLE condition", str(ctx.exception))

        # 6b. Attempt to release when asset itself became UNSERVICEABLE
        Asset.objects.filter(pk=self.serviceable_asset.pk).update(condition=Asset.Condition.UNSERVICEABLE)
        with self.assertRaises(ValidationError) as ctx:
            borrowing_services.release_asset(
                borrowing=borrowing,
                released_by=self.admin,
                condition_at_release=Asset.Condition.GOOD
            )
        self.assertIn("is unserviceable", str(ctx.exception))

    # --------------------------------------------------------------------------
    # 7. Student Reservations: get_reservable_assets, check_asset_availability, release_equipment
    # --------------------------------------------------------------------------
    def test_get_reservable_assets_excludes_unserviceable(self):
        qs = student_res_services.get_reservable_assets()
        self.assertIn(self.serviceable_asset, qs)
        self.assertNotIn(self.unserviceable_asset, qs)

    def test_check_asset_availability_rejects_unserviceable(self):
        is_avail, reason = student_res_services.check_asset_availability(
            asset=self.unserviceable_asset,
            requested_pickup=self.now + timedelta(hours=1),
            requested_return=self.now + timedelta(hours=3)
        )
        self.assertFalse(is_avail)
        self.assertIn("is unserviceable", reason.lower())

    def test_release_equipment_rejects_unserviceable_asset_or_condition(self):
        reservation = StudentReservation.objects.create(
            student_id='2024-0001',
            student_name='Maria Clara',
            course_year_section='BSBA 2-A',
            email='maria@cba.edu',
            contact_number='09181112222',
            category=self.cat,
            equipment_type='Laptop',
            requested_pickup=self.now + timedelta(hours=1),
            requested_return=self.now + timedelta(hours=3),
            purpose='Class presentation',
            status=StudentReservation.Status.PENDING
        )
        student_res_services.approve_reservation(
            reservation=reservation,
            asset=self.serviceable_asset,
            reviewed_by=self.admin
        )

        # 7a. Releasing with condition_at_release=UNSERVICEABLE
        with self.assertRaises(ValidationError) as ctx:
            student_res_services.release_equipment(
                reservation=reservation,
                released_by=self.admin,
                condition_at_release=Asset.Condition.UNSERVICEABLE,
                id_deposited=True
            )
        self.assertIn("in UNSERVICEABLE condition", str(ctx.exception))

        # 7b. Releasing when physical asset is UNSERVICEABLE
        Asset.objects.filter(pk=self.serviceable_asset.pk).update(condition=Asset.Condition.UNSERVICEABLE)
        with self.assertRaises(ValidationError) as ctx:
            student_res_services.release_equipment(
                reservation=reservation,
                released_by=self.admin,
                condition_at_release=Asset.Condition.GOOD,
                id_deposited=True
            )
        self.assertIn("is unserviceable", str(ctx.exception))
