import io
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, Client
from django.core.management import call_command, CommandError
from django.urls import reverse

from apps.accounts.models import User
from apps.organizations.models import Department, Location
from apps.inventory.models import AssetCategory, Brand, Asset
from apps.student_reservations import services


class SeedDemoEquipmentHardenedTestCase(TestCase):
    """
    Regression and safety test suite for seed_demo_equipment command:
    1. Accidental local SQLite application is rejected.
    2. Missing confirmation flags (--apply or --confirm-neon) are rejected.
    3. Dry-run by default performs zero writes.
    4. Successful application on verified host provisions categories, brands, and assets.
    5. Second seed execution creates zero duplicates (idempotency).
    6. Existing demo assets retaining operational states (BORROWED, DAMAGED, is_reservable=False).
    7. Existing non-demo categories and assets remain untouched.
    8. Conflicting category codes, names, or deactivated states abort before writing.
    9. Catalog integration renders correctly with demonstration data.
    """

    def setUp(self):
        self.client = Client()

    # --------------------------------------------------------------------------
    # 1. Target Host & Confirmation Flag Safety Guards
    # --------------------------------------------------------------------------

    def test_accidental_sqlite_application_rejected(self):
        """Applying against local SQLite or non-Neon database must be aborted with CommandError."""
        with self.assertRaises(CommandError) as ctx:
            call_command('seed_demo_equipment', apply=True, confirm_neon=True)
        self.assertIn("Target database is not a verified Neon PostgreSQL instance", str(ctx.exception))
        self.assertIn("sqlite", str(ctx.exception).lower())

    def test_missing_confirm_neon_flag_rejected(self):
        """Passing --apply without --confirm-neon must be rejected before any checks."""
        with self.assertRaises(CommandError) as ctx:
            call_command('seed_demo_equipment', apply=True)
        self.assertIn("Database writes require BOTH --apply and --confirm-neon", str(ctx.exception))

    def test_missing_apply_flag_rejected(self):
        """Passing --confirm-neon without --apply must be rejected."""
        with self.assertRaises(CommandError) as ctx:
            call_command('seed_demo_equipment', confirm_neon=True)
        self.assertIn("Database writes require BOTH --apply and --confirm-neon", str(ctx.exception))

    # --------------------------------------------------------------------------
    # 2. Dry-Run Default Safety
    # --------------------------------------------------------------------------

    def test_dry_run_default_makes_no_database_changes(self):
        """Executing without write flags must run in simulation mode without writing to DB."""
        out = io.StringIO()
        call_command('seed_demo_equipment', stdout=out)
        output_str = out.getvalue()

        self.assertIn("DRY RUN SIMULATION", output_str)
        self.assertIn("No database records will be created, modified, or deleted", output_str)
        self.assertIn("Would create", output_str)

        self.assertFalse(AssetCategory.objects.filter(code='PRJ').exists())
        self.assertFalse(AssetCategory.objects.filter(code='AUD').exists())
        self.assertFalse(AssetCategory.objects.filter(code='ACC').exists())
        self.assertFalse(AssetCategory.objects.filter(code='DSP').exists())
        self.assertEqual(Asset.objects.filter(property_number__startswith='DEMO-').count(), 0)

    # --------------------------------------------------------------------------
    # 3. Successful Seeding on Verified Host (Mocked Neon Check)
    # --------------------------------------------------------------------------

    @patch('apps.student_reservations.management.commands.seed_demo_equipment.is_valid_neon_database', return_value=True)
    def test_apply_mode_creates_expected_categories_brands_assets(self, mock_is_neon):
        """Executing with paired flags on verified Neon creates categories, brands, and demo assets."""
        out = io.StringIO()
        call_command('seed_demo_equipment', apply=True, confirm_neon=True, stdout=out)
        output_str = out.getvalue()

        self.assertIn("APPLY MODE - NEON", output_str)
        self.assertIn("Demonstration equipment data successfully prepared", output_str)

        for code, name in [
            ('PRJ', 'Projectors'),
            ('AUD', 'Audio Equipment'),
            ('ACC', 'Presentation Accessories'),
            ('DSP', 'Display Equipment'),
        ]:
            cat = AssetCategory.objects.filter(code=code).first()
            self.assertIsNotNone(cat, f"Category {code} was not created.")
            self.assertEqual(cat.name, name)
            self.assertTrue(cat.is_active)
            self.assertTrue(cat.is_reservable)

        for b in ['Epson', 'Sony', 'Logitech', 'Generic']:
            self.assertTrue(Brand.objects.filter(name=b).exists(), f"Brand {b} was not created.")

        expected_props = [
            'DEMO-PRJ-001',
            'DEMO-PRJ-002',
            'DEMO-AUD-001',
            'DEMO-AUD-002',
            'DEMO-ACC-001',
            'DEMO-ACC-002',
        ]
        self.assertEqual(Asset.objects.filter(property_number__startswith='DEMO-').count(), 6)

        for prop_num in expected_props:
            asset = Asset.objects.filter(property_number=prop_num).first()
            self.assertIsNotNone(asset, f"Asset {prop_num} was not found.")
            self.assertEqual(asset.status, Asset.Status.AVAILABLE)
            self.assertTrue(asset.is_reservable)
            self.assertTrue(asset.asset_code.startswith('CBA-'))
            self.assertIsNotNone(asset.department)
            self.assertIsNotNone(asset.current_location)

        from apps.inventory.models import EquipmentType
        prj_cat = AssetCategory.objects.get(code='PRJ')
        self.assertTrue(EquipmentType.objects.filter(category=prj_cat, name='Projector').exists())
        aud_cat = AssetCategory.objects.get(code='AUD')
        self.assertTrue(EquipmentType.objects.filter(category=aud_cat, name='Portable Speaker').exists())
        self.assertTrue(EquipmentType.objects.filter(category=aud_cat, name='Wireless Microphone').exists())

        demo_prj1 = Asset.objects.get(property_number='DEMO-PRJ-001')
        self.assertIsNotNone(demo_prj1.equipment_type)
        self.assertEqual(demo_prj1.equipment_type.name, 'Projector')

    # --------------------------------------------------------------------------
    # 4. Strict Idempotency & Zero Duplication
    # --------------------------------------------------------------------------

    @patch('apps.student_reservations.management.commands.seed_demo_equipment.is_valid_neon_database', return_value=True)
    def test_idempotency_rerun_creates_no_duplicates(self, mock_is_neon):
        """Rerunning seed_demo_equipment must not duplicate any category, brand, or asset."""
        from apps.inventory.models import EquipmentType
        call_command('seed_demo_equipment', apply=True, confirm_neon=True, stdout=io.StringIO())

        cat_count_before = AssetCategory.objects.count()
        brand_count_before = Brand.objects.count()
        type_count_before = EquipmentType.objects.count()
        asset_count_before = Asset.objects.count()

        out = io.StringIO()
        call_command('seed_demo_equipment', apply=True, confirm_neon=True, stdout=out)
        output_str = out.getvalue()

        self.assertEqual(AssetCategory.objects.count(), cat_count_before)
        self.assertEqual(Brand.objects.count(), brand_count_before)
        self.assertEqual(EquipmentType.objects.count(), type_count_before)
        self.assertEqual(Asset.objects.count(), asset_count_before)

        self.assertIn("Demo assets created:         0", output_str)
        self.assertIn("Demo assets preserved:       6", output_str)

    # --------------------------------------------------------------------------
    # 5. Immutability of Existing Demo Asset States
    # --------------------------------------------------------------------------

    @patch('apps.student_reservations.management.commands.seed_demo_equipment.is_valid_neon_database', return_value=True)
    def test_existing_demo_asset_retains_status_availability_condition(self, mock_is_neon):
        """
        Hardened safety rule:
        Existing demo assets must NEVER have their status, availability, condition,
        or assignment reset by rerunning the seeder.
        """
        # Seed initial assets
        call_command('seed_demo_equipment', apply=True, confirm_neon=True, stdout=io.StringIO())

        # Simulate ongoing student checkout and maintenance
        asset1 = Asset.objects.get(property_number='DEMO-PRJ-001')
        asset1.status = Asset.Status.BORROWED
        asset1.is_reservable = False
        asset1.condition = Asset.Condition.FAIR
        asset1.remarks = "Loaned out for college conference."
        asset1.save()

        asset2 = Asset.objects.get(property_number='DEMO-AUD-001')
        asset2.status = Asset.Status.DAMAGED
        asset2.is_reservable = False
        asset2.save()

        # Re-run seeder
        out = io.StringIO()
        call_command('seed_demo_equipment', apply=True, confirm_neon=True, stdout=out)
        output_str = out.getvalue()

        # Confirm neither asset was reset to AVAILABLE or is_reservable=True
        asset1.refresh_from_db()
        self.assertEqual(asset1.status, Asset.Status.BORROWED)
        self.assertFalse(asset1.is_reservable)
        self.assertEqual(asset1.condition, Asset.Condition.FAIR)
        self.assertEqual(asset1.remarks, "Loaned out for college conference.")

        asset2.refresh_from_db()
        self.assertEqual(asset2.status, Asset.Status.DAMAGED)
        self.assertFalse(asset2.is_reservable)

        self.assertIn("Preserved existing state (Status: Borrowed, Reservable: False)", output_str)

    # --------------------------------------------------------------------------
    # 6. Preservation of Non-Demo Inventory
    # --------------------------------------------------------------------------

    @patch('apps.student_reservations.management.commands.seed_demo_equipment.is_valid_neon_database', return_value=True)
    def test_preserves_pre_existing_non_demo_inventory(self, mock_is_neon):
        """Non-demo inventory and categories must remain completely untouched."""
        dept = Department.objects.create(code='EXISTING_DEPT', name='Existing Department')
        cat = AssetCategory.objects.create(code='FN_TEST', name='Furniture Test', is_reservable=False)
        non_demo_asset = Asset.objects.create(
            property_number='NON-DEMO-001',
            item_name='Office Desk Executive',
            category=cat,
            department=dept,
            is_reservable=False,
            status=Asset.Status.BORROWED,
        )

        call_command('seed_demo_equipment', apply=True, confirm_neon=True, stdout=io.StringIO())

        non_demo_asset.refresh_from_db()
        self.assertEqual(non_demo_asset.item_name, 'Office Desk Executive')
        self.assertFalse(non_demo_asset.is_reservable)
        self.assertEqual(non_demo_asset.status, Asset.Status.BORROWED)
        self.assertEqual(non_demo_asset.property_number, 'NON-DEMO-001')

        cat.refresh_from_db()
        self.assertEqual(cat.code, 'FN_TEST')
        self.assertFalse(cat.is_reservable)

    # --------------------------------------------------------------------------
    # 7. Category Conflict Detection & Abort Safety
    # --------------------------------------------------------------------------

    @patch('apps.student_reservations.management.commands.seed_demo_equipment.is_valid_neon_database', return_value=True)
    def test_conflicting_category_code_aborts_without_writing(self, mock_is_neon):
        """If a category code matches but has a conflicting name, must abort without writing."""
        # Pre-existing category with code 'PRJ' but different name
        AssetCategory.objects.create(code='PRJ', name='Custom Projection Hardware', is_reservable=True)

        with self.assertRaises(CommandError) as ctx:
            call_command('seed_demo_equipment', apply=True, confirm_neon=True)

        self.assertIn("SAFETY ABORT: Conflicting category data detected", str(ctx.exception))
        self.assertIn("Code conflict", str(ctx.exception))

        # Ensure no demo assets were created
        self.assertEqual(Asset.objects.filter(property_number__startswith='DEMO-').count(), 0)

    @patch('apps.student_reservations.management.commands.seed_demo_equipment.is_valid_neon_database', return_value=True)
    def test_conflicting_category_name_aborts_without_writing(self, mock_is_neon):
        """If a category name matches but has a conflicting code, must abort without writing."""
        # Pre-existing category with name 'Projectors' but different code
        AssetCategory.objects.create(code='PROJ_ALT', name='Projectors', is_reservable=True)

        with self.assertRaises(CommandError) as ctx:
            call_command('seed_demo_equipment', apply=True, confirm_neon=True)

        self.assertIn("SAFETY ABORT: Conflicting category data detected", str(ctx.exception))
        self.assertIn("Name conflict", str(ctx.exception))

        # Ensure no demo assets were created
        self.assertEqual(Asset.objects.filter(property_number__startswith='DEMO-').count(), 0)

    @patch('apps.student_reservations.management.commands.seed_demo_equipment.is_valid_neon_database', return_value=True)
    def test_deactivated_or_non_reservable_category_aborts_without_writing(self, mock_is_neon):
        """Existing categories must not be silently reactivated or marked reservable."""
        # Pre-existing category 'Projectors' (PRJ) that is marked non-reservable
        AssetCategory.objects.create(code='PRJ', name='Projectors', is_active=True, is_reservable=False)

        with self.assertRaises(CommandError) as ctx:
            call_command('seed_demo_equipment', apply=True, confirm_neon=True)

        self.assertIn("SAFETY ABORT: Conflicting category data detected", str(ctx.exception))
        self.assertIn("Policy conflict", str(ctx.exception))

        # Category state must remain un-tampered
        cat = AssetCategory.objects.get(code='PRJ')
        self.assertFalse(cat.is_reservable)

    # --------------------------------------------------------------------------
    # 8. Catalog Integration
    # --------------------------------------------------------------------------

    @patch('apps.student_reservations.management.commands.seed_demo_equipment.is_valid_neon_database', return_value=True)
    def test_catalog_integration_renders_seeded_equipment(self, mock_is_neon):
        """Catalog renders category cards and eliminates 'No Equipment Categories Available'."""
        call_command('seed_demo_equipment', apply=True, confirm_neon=True, stdout=io.StringIO())

        reservable_cats = services.get_reservable_categories()
        self.assertEqual(reservable_cats.count(), 4)

        reservable_assets = services.get_reservable_assets()
        self.assertEqual(reservable_assets.count(), 6)

        response = self.client.get(reverse('student_reservations:catalog'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "No Equipment Categories Available")
        self.assertContains(response, "Projectors")
        self.assertContains(response, "Audio Equipment")
        self.assertContains(response, "Presentation Accessories")
        self.assertContains(response, "Display Equipment")
