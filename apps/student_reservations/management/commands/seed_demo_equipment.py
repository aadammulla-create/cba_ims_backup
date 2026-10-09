from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.conf import settings

from apps.accounts.models import User
from apps.organizations.models import Department, Location
from apps.inventory.models import AssetCategory, Brand, Asset, EquipmentType
from apps.audit.utils import log_action


def is_valid_neon_database(db_alias='default'):
    """
    Validates that the active database is PostgreSQL hosted on Neon (*.neon.tech).
    Used to prevent accidental database writes against local SQLite or unrecognized hosts.
    """
    db_settings = settings.DATABASES.get(db_alias, {})
    engine = db_settings.get('ENGINE', '')
    host = (db_settings.get('HOST') or '').strip().lower()

    is_postgres = 'postgresql' in engine or 'postgres' in engine
    is_neon = host.endswith('.neon.tech') or '.neon.tech' in host

    return is_postgres and is_neon


class Command(BaseCommand):
    help = (
        "Idempotently prepare fictional demonstration equipment for the CBA Student Equipment Reservation Portal. "
        "Defaults to dry-run simulation mode. Writes require BOTH --apply and --confirm-neon against Neon PostgreSQL."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Request database write. Must be paired with --confirm-neon to execute.',
        )
        parser.add_argument(
            '--confirm-neon',
            action='store_true',
            help='Explicit confirmation to write to hosted Neon PostgreSQL (*.neon.tech).',
        )

    def handle(self, *args, **options):
        apply_requested = options.get('apply', False)
        confirm_neon = options.get('confirm_neon', False)

        # 1. Flag Pairing Safety Guard
        if apply_requested and not confirm_neon:
            raise CommandError(
                "SAFETY ERROR: Database writes require BOTH --apply and --confirm-neon flags.\n"
                "Execution aborted to prevent unintended changes."
            )

        if confirm_neon and not apply_requested:
            raise CommandError(
                "SAFETY ERROR: --confirm-neon was supplied without --apply.\n"
                "Database writes require BOTH --apply and --confirm-neon flags."
            )

        apply_mode = apply_requested and confirm_neon

        # 2. Target Database Inspection & Neon Host Verification
        db_settings = settings.DATABASES.get('default', {})
        db_engine = db_settings.get('ENGINE', '')
        db_engine_short = db_engine.split('.')[-1]
        db_name = db_settings.get('NAME', '')
        db_host = db_settings.get('HOST', 'localhost') or 'localhost'

        if apply_mode:
            if not is_valid_neon_database():
                raise CommandError(
                    f"SAFETY ABORT: Target database is not a verified Neon PostgreSQL instance.\n"
                    f"  Engine: '{db_engine}'\n"
                    f"  Host:   '{db_host}'\n"
                    f"Database writes are strictly restricted to Neon PostgreSQL (*.neon.tech).\n"
                    f"Application to local SQLite or non-Neon hosts is rejected."
                )

        # Header output (never logs passwords or secrets)
        self.stdout.write("=" * 72)
        if apply_mode:
            self.stdout.write(self.style.SUCCESS("CBA IMS — Seed Demonstration Equipment (APPLY MODE - NEON)"))
        else:
            self.stdout.write(self.style.WARNING("CBA IMS — Seed Demonstration Equipment (DRY RUN SIMULATION)"))
        self.stdout.write("=" * 72)
        self.stdout.write(f"Target Database Engine: {db_engine_short}")
        self.stdout.write(f"Target Database Name:   {db_name}")
        self.stdout.write(f"Target Database Host:   {db_host}")

        if not apply_mode:
            self.stdout.write(self.style.NOTICE(
                "\nSIMULATION NOTICE: Running in dry-run mode by default.\n"
                "No database records will be created, modified, or deleted.\n"
                "To write to Neon PostgreSQL, both flags are required:\n"
                "  python manage.py seed_demo_equipment --apply --confirm-neon\n"
            ))
        else:
            self.stdout.write(self.style.NOTICE(
                "\nEXECUTION NOTICE: Committing demonstration records to Neon inside an atomic transaction.\n"
            ))

        # 3. Existing Baseline Check
        existing_total_assets = Asset.objects.count()
        existing_non_demo_assets = Asset.objects.exclude(property_number__startswith='DEMO-').count()
        existing_demo_assets = Asset.objects.filter(property_number__startswith='DEMO-').count()

        self.stdout.write("--- Pre-Seed Database Inspection ---")
        self.stdout.write(f"Total existing assets in database:     {existing_total_assets}")
        self.stdout.write(f"Existing non-demo assets (preserved):   {existing_non_demo_assets}")
        self.stdout.write(f"Existing demo assets (to verify):       {existing_demo_assets}\n")

        # 4. Specification
        demo_categories_spec = [
            {
                'code': 'PRJ',
                'name': 'Projectors',
                'description': 'Digital LCD and DLP multimedia projectors for classroom instruction and auditorium presentations.',
                'is_active': True,
                'is_reservable': True,
            },
            {
                'code': 'AUD',
                'name': 'Audio Equipment',
                'description': 'Portable public address sound systems, active speakers, and wireless microphone sets.',
                'is_active': True,
                'is_reservable': True,
            },
            {
                'code': 'ACC',
                'name': 'Presentation Accessories',
                'description': 'Wireless laser presentation clickers, HDMI/USB-C display adapters, and extension cables.',
                'is_active': True,
                'is_reservable': True,
            },
            {
                'code': 'DSP',
                'name': 'Display Equipment',
                'description': 'Portable tripod projection screens, rolling monitor stands, and auxiliary display units.',
                'is_active': True,
                'is_reservable': True,
            },
        ]

        demo_brands_spec = ['Epson', 'Sony', 'Logitech', 'Generic']

        demo_equipment_types_spec = [
            {
                'category_code': 'PRJ',
                'name': 'Projector',
                'description': 'Multimedia LCD and DLP digital video projector.',
            },
            {
                'category_code': 'AUD',
                'name': 'Portable Speaker',
                'description': 'Rechargeable active speaker for audio playback and voice amplification.',
            },
            {
                'category_code': 'AUD',
                'name': 'Wireless Microphone',
                'description': 'Handheld UHF wireless microphone transmitter and receiver set.',
            },
            {
                'category_code': 'ACC',
                'name': 'Display Adapter',
                'description': 'USB-C / HDMI video display conversion dongle.',
            },
            {
                'category_code': 'ACC',
                'name': 'Wireless Presenter Clicker',
                'description': 'Handheld presentation slide advancer with integrated laser pointer.',
            },
            {
                'category_code': 'DSP',
                'name': 'Tripod Projection Screen',
                'description': 'Portable pull-up tripod matte white projection screen.',
            },
        ]

        demo_assets_spec = [
            {
                'property_number': 'DEMO-PRJ-001',
                'item_name': 'Epson EB-E01 Projector',
                'category_code': 'PRJ',
                'brand_name': 'Epson',
                'equipment_type_name': 'Projector',
                'model': 'EB-E01 XGA',
                'serial_number': 'DEMO-SN-PRJ001',
                'condition': Asset.Condition.GOOD,
                'status': Asset.Status.AVAILABLE,
                'is_reservable': True,
                'acquisition_date': date(2025, 3, 10),
                'acquisition_cost': Decimal('22500.00'),
                'supplier': 'Columbia Technologies Inc. (Demo)',
                'description': 'Fictional 3,300 lumens XGA 3LCD multimedia projector for classroom presentations.',
                'remarks': 'Demonstration equipment for student reservations portal.',
            },
            {
                'property_number': 'DEMO-PRJ-002',
                'item_name': 'Epson EB-X51 Projector',
                'category_code': 'PRJ',
                'brand_name': 'Epson',
                'equipment_type_name': 'Projector',
                'model': 'EB-X51 XGA',
                'serial_number': 'DEMO-SN-PRJ002',
                'condition': Asset.Condition.GOOD,
                'status': Asset.Status.AVAILABLE,
                'is_reservable': True,
                'acquisition_date': date(2025, 4, 15),
                'acquisition_cost': Decimal('26900.00'),
                'supplier': 'Columbia Technologies Inc. (Demo)',
                'description': 'Fictional 3,800 lumens high-brightness presentation projector with HDMI input.',
                'remarks': 'Demonstration equipment for student reservations portal.',
            },
            {
                'property_number': 'DEMO-AUD-001',
                'item_name': 'Portable Bluetooth Speaker',
                'category_code': 'AUD',
                'brand_name': 'Sony',
                'equipment_type_name': 'Portable Speaker',
                'model': 'SRS-XP500',
                'serial_number': 'DEMO-SN-AUD001',
                'condition': Asset.Condition.GOOD,
                'status': Asset.Status.AVAILABLE,
                'is_reservable': True,
                'acquisition_date': date(2025, 5, 20),
                'acquisition_cost': Decimal('16500.00'),
                'supplier': 'Sony Authorized Store (Demo)',
                'description': 'Fictional portable rechargeable speaker with dual mic inputs for college activities.',
                'remarks': 'Demonstration equipment for student reservations portal.',
            },
            {
                'property_number': 'DEMO-AUD-002',
                'item_name': 'Wireless Microphone Set',
                'category_code': 'AUD',
                'brand_name': 'Sony',
                'equipment_type_name': 'Wireless Microphone',
                'model': 'UHF Dual Wireless Mic',
                'serial_number': 'DEMO-SN-AUD002',
                'condition': Asset.Condition.GOOD,
                'status': Asset.Status.AVAILABLE,
                'is_reservable': True,
                'acquisition_date': date(2025, 5, 20),
                'acquisition_cost': Decimal('8500.00'),
                'supplier': 'Sony Authorized Store (Demo)',
                'description': 'Fictional dual handheld wireless UHF microphones with receiver base and accessories.',
                'remarks': 'Demonstration equipment for student reservations portal.',
            },
            {
                'property_number': 'DEMO-ACC-001',
                'item_name': 'USB-C to HDMI Multi-Port Adapter',
                'category_code': 'ACC',
                'brand_name': 'Generic',
                'equipment_type_name': 'Display Adapter',
                'model': '4K Type-C Multiport',
                'serial_number': 'DEMO-SN-ACC001',
                'condition': Asset.Condition.NEW,
                'status': Asset.Status.AVAILABLE,
                'is_reservable': True,
                'acquisition_date': date(2025, 6, 1),
                'acquisition_cost': Decimal('1250.00'),
                'supplier': 'Generic Computer Supplies (Demo)',
                'description': 'Fictional USB-C to HDMI display adapter dongle with 4K output support.',
                'remarks': 'Demonstration equipment for student reservations portal.',
            },
            {
                'property_number': 'DEMO-ACC-002',
                'item_name': 'Wireless Presentation Clicker',
                'category_code': 'ACC',
                'brand_name': 'Logitech',
                'equipment_type_name': 'Wireless Presenter Clicker',
                'model': 'R500s Laser Pointer',
                'serial_number': 'DEMO-SN-ACC002',
                'condition': Asset.Condition.GOOD,
                'status': Asset.Status.AVAILABLE,
                'is_reservable': True,
                'acquisition_date': date(2025, 6, 1),
                'acquisition_cost': Decimal('1850.00'),
                'supplier': 'Logitech Philippines (Demo)',
                'description': 'Fictional 2.4GHz wireless presenter remote with red laser pointer.',
                'remarks': 'Demonstration equipment for student reservations portal.',
            },
        ]

        # 5. Pre-Execution Conflict Validation
        # Validates that no existing categories have conflicting codes/names or deactivated states
        # before any database write occurs.
        self.stdout.write("--- 1. Category Conflict Validation ---")
        category_conflicts = []
        categories_map = {}

        for cat_spec in demo_categories_spec:
            code = cat_spec['code']
            name = cat_spec['name']

            cat_by_code = AssetCategory.objects.filter(code=code).first()
            cat_by_name = AssetCategory.objects.filter(name=name).first()

            if cat_by_code and not cat_by_name:
                category_conflicts.append(
                    f"Code conflict: Category code '{code}' is already used by category '{cat_by_code.name}'."
                )
            elif not cat_by_code and cat_by_name:
                category_conflicts.append(
                    f"Name conflict: Category name '{name}' already exists with different code '{cat_by_name.code}'."
                )
            elif cat_by_code and cat_by_name:
                if cat_by_code.pk != cat_by_name.pk:
                    category_conflicts.append(
                        f"Cross conflict: Code '{code}' belongs to '{cat_by_code.name}', "
                        f"while name '{name}' belongs to category '{cat_by_name.code}'."
                    )
                else:
                    # Same category matched by both code and name.
                    # Verify it is not deactivated or non-reservable.
                    # Existing categories must not be silently renamed, reactivated, or marked reservable.
                    if not cat_by_code.is_active:
                        category_conflicts.append(
                            f"Policy conflict: Category '{name}' ({code}) exists but is inactive (is_active=False). "
                            "It must not be silently reactivated."
                        )
                    elif not cat_by_code.is_reservable:
                        category_conflicts.append(
                            f"Policy conflict: Category '{name}' ({code}) exists but is non-reservable (is_reservable=False). "
                            "It must not be silently marked reservable."
                        )
                    else:
                        categories_map[code] = cat_by_code

        if category_conflicts:
            for conflict_msg in category_conflicts:
                self.stdout.write(self.style.ERROR(f"  [CONFLICT] {conflict_msg}"))
            raise CommandError(
                "SAFETY ABORT: Conflicting category data detected:\n"
                + "\n".join(f" - {c}" for c in category_conflicts)
                + "\nNo changes were written to the database."
            )
        else:
            self.stdout.write(self.style.SUCCESS("  Category validation passed: No conflicts detected."))

        # 6. Execution Plan
        def execute_plan():
            admin_user = User.objects.filter(role=User.Role.ADMIN).first()

            # A. Department Resolution
            self.stdout.write("\n--- 2. Organizational Hierarchy Resolution ---")
            dept = (
                Department.objects.filter(code='CBA').first()
                or Department.objects.filter(name__icontains='College of Business Administration').first()
                or Department.objects.filter(is_active=True).first()
            )
            if dept:
                self.stdout.write(f"  Department: Found existing '{dept.name}' ({dept.code})")
            else:
                if apply_mode:
                    dept = Department.objects.create(
                        code='CBA',
                        name='College of Business Administration',
                        description='College of Business Administration Main Office',
                        is_active=True
                    )
                    self.stdout.write(self.style.SUCCESS(f"  Department: Created '{dept.name}' ({dept.code})"))
                else:
                    self.stdout.write(self.style.WARNING("  Department: None found -> Would create 'College of Business Administration' (CBA)"))

            # B. Location Resolution
            loc = (
                Location.objects.filter(name__icontains='Property').first()
                or Location.objects.filter(is_active=True).first()
            )
            if loc:
                self.stdout.write(f"  Location:   Found existing '{loc.name}'")
            else:
                if apply_mode:
                    loc = Location.objects.create(
                        name='CBA Property Office',
                        building='CBA Main',
                        room_number='101',
                        department=dept,
                        description='Central equipment custody and checkout location',
                        is_active=True
                    )
                    self.stdout.write(self.style.SUCCESS(f"  Location:   Created '{loc.name}'"))
                else:
                    self.stdout.write(self.style.WARNING("  Location:   None found -> Would create 'CBA Property Office'"))

            # C. Category Application
            self.stdout.write("\n--- 3. Asset Categories ---")
            cats_created = 0
            cats_verified = 0

            for cat_spec in demo_categories_spec:
                code = cat_spec['code']
                name = cat_spec['name']

                cat = categories_map.get(code)
                if cat:
                    cats_verified += 1
                    self.stdout.write(f"  [{code}] {name}: Verified existing & reservable")
                else:
                    if apply_mode:
                        cat = AssetCategory.objects.create(**cat_spec)
                        categories_map[code] = cat
                        cats_created += 1
                        self.stdout.write(self.style.SUCCESS(f"  [{code}] {name}: Created reservable category"))
                    else:
                        cats_created += 1
                        self.stdout.write(self.style.WARNING(f"  [{code}] {name}: Not found -> Would create reservable category"))

            # D. Brand Application
            self.stdout.write("\n--- 4. Equipment Brands ---")
            brands_map = {}
            brands_created = 0
            brands_verified = 0

            for brand_name in demo_brands_spec:
                brand = Brand.objects.filter(name=brand_name).first()
                if brand:
                    brands_map[brand_name] = brand
                    brands_verified += 1
                    self.stdout.write(f"  Brand '{brand_name}': Verified existing")
                else:
                    if apply_mode:
                        brand = Brand.objects.create(name=brand_name, is_active=True)
                        brands_map[brand_name] = brand
                        brands_created += 1
                        self.stdout.write(self.style.SUCCESS(f"  Brand '{brand_name}': Created brand"))
                    else:
                        brands_created += 1
                        self.stdout.write(self.style.WARNING(f"  Brand '{brand_name}': Not found -> Would create brand"))

            # E. Equipment Types Application
            self.stdout.write("\n--- 5. Equipment Types ---")
            types_map = {}
            types_created = 0
            types_verified = 0

            for type_spec in demo_equipment_types_spec:
                cat_code = type_spec['category_code']
                name = type_spec['name']
                cat = categories_map.get(cat_code) or AssetCategory.objects.filter(code=cat_code).first()

                eq_type = EquipmentType.objects.filter(category=cat, name=name).first() if cat else None
                if eq_type:
                    types_map[(cat_code, name)] = eq_type
                    types_verified += 1
                    self.stdout.write(f"  [{cat_code}] {name}: Verified existing")
                else:
                    if apply_mode and cat:
                        eq_type = EquipmentType.objects.create(
                            category=cat,
                            name=name,
                            description=type_spec.get('description', ''),
                            is_active=True,
                        )
                        types_map[(cat_code, name)] = eq_type
                        types_created += 1
                        self.stdout.write(self.style.SUCCESS(f"  [{cat_code}] {name}: Created equipment type"))
                    else:
                        types_created += 1
                        self.stdout.write(self.style.WARNING(f"  [{cat_code}] {name}: Not found -> Would create equipment type under '{cat_code}'"))

            # F. Demonstration Assets Application
            self.stdout.write("\n--- 6. Physical Demonstration Assets ---")
            assets_created = 0
            assets_verified = 0

            for asset_spec in demo_assets_spec:
                prop_num = asset_spec['property_number']
                cat_code = asset_spec['category_code']
                brand_name = asset_spec['brand_name']

                cat = categories_map.get(cat_code) or AssetCategory.objects.filter(code=cat_code).first()
                brand = brands_map.get(brand_name) or Brand.objects.filter(name=brand_name).first()

                existing_asset = Asset.objects.filter(property_number=prop_num).first()

                if existing_asset:
                    assets_verified += 1
                    # HARDENED RULE: Existing demo assets must NEVER have their current status,
                    # availability (is_reservable), condition, assignment, or reservation-related
                    # fields reset or overwritten by rerunning the seeder.
                    eq_type_name = asset_spec.get('equipment_type_name')
                    eq_type = types_map.get((cat_code, eq_type_name)) or (
                        EquipmentType.objects.filter(category=cat, name=eq_type_name).first() if cat and eq_type_name else None
                    )
                    if eq_type and not existing_asset.equipment_type:
                        if apply_mode:
                            existing_asset.equipment_type = eq_type
                            existing_asset.save(update_fields=['equipment_type'])
                            self.stdout.write(
                                f"  [{prop_num}] {existing_asset.asset_code} — {existing_asset.item_name}: "
                                f"Associated with EquipmentType '{eq_type.name}' (preserved status & availability)"
                            )
                        else:
                            self.stdout.write(
                                f"  [{prop_num}] {existing_asset.asset_code} — {existing_asset.item_name}: "
                                f"Found -> Would associate with EquipmentType '{eq_type.name}' (preserved status & availability)"
                            )
                    else:
                        if apply_mode:
                            self.stdout.write(
                                f"  [{prop_num}] {existing_asset.asset_code} — {existing_asset.item_name}: "
                                f"Preserved existing state (Status: {existing_asset.get_status_display()}, "
                                f"Reservable: {existing_asset.is_reservable})"
                            )
                        else:
                            self.stdout.write(
                                f"  [{prop_num}] {existing_asset.asset_code} — {existing_asset.item_name}: "
                                f"Found -> Would preserve existing state without resetting status/availability"
                            )
                else:
                    assets_created += 1
                    eq_type_name = asset_spec.get('equipment_type_name')
                    eq_type = types_map.get((cat_code, eq_type_name)) or (
                        EquipmentType.objects.filter(category=cat, name=eq_type_name).first() if cat and eq_type_name else None
                    )
                    if apply_mode:
                        new_asset = Asset(
                            property_number=prop_num,
                            item_name=asset_spec['item_name'],
                            category=cat,
                            brand=brand,
                            equipment_type=eq_type,
                            model=asset_spec['model'],
                            serial_number=asset_spec['serial_number'],
                            condition=asset_spec['condition'],
                            status=asset_spec['status'],
                            is_reservable=True,
                            department=dept,
                            current_location=loc,
                            description=asset_spec['description'],
                            remarks=asset_spec['remarks'],
                            acquisition_cost=asset_spec['acquisition_cost'],
                            acquisition_date=asset_spec['acquisition_date'],
                            supplier=asset_spec['supplier'],
                            created_by=admin_user,
                        )
                        new_asset.save()  # Auto-generates asset_code (e.g. CBA-PRJ-00001)

                        if admin_user:
                            try:
                                log_action(admin_user, 'ASSET_CREATED', new_asset, changes={'seed_demo': True})
                            except Exception:
                                pass

                        self.stdout.write(self.style.SUCCESS(
                            f"  [{prop_num}] {new_asset.asset_code} — {new_asset.item_name}: Created (Reservable & Available)"
                        ))
                    else:
                        self.stdout.write(self.style.WARNING(
                            f"  [{prop_num}] {asset_spec['item_name']} (Category: {cat_code}): Not found -> Would create (Reservable & Available)"
                        ))

            # G. Final Audit and Summary
            self.stdout.write("\n" + "=" * 72)
            if apply_mode:
                self.stdout.write(self.style.SUCCESS("SUMMARY (CHANGES COMMITTED TO NEON):"))
            else:
                self.stdout.write(self.style.WARNING("SUMMARY (DRY RUN SIMULATION - NO WRITES):"))
            self.stdout.write(f"  Categories created:          {cats_created}")
            self.stdout.write(f"  Categories verified:         {cats_verified}")
            self.stdout.write(f"  Brands created:              {brands_created}")
            self.stdout.write(f"  Brands verified:             {brands_verified}")
            self.stdout.write(f"  Equipment types created:     {types_created}")
            self.stdout.write(f"  Equipment types verified:    {types_verified}")
            self.stdout.write(f"  Demo assets created:         {assets_created}")
            self.stdout.write(f"  Demo assets preserved:       {assets_verified}")
            self.stdout.write(f"  Non-demo assets preserved:   {existing_non_demo_assets}")
            self.stdout.write("=" * 72)

            if not apply_mode:
                self.stdout.write(self.style.NOTICE(
                    "\nTo apply these demonstration records to Neon PostgreSQL, run:\n"
                    "  python manage.py seed_demo_equipment --apply --confirm-neon\n"
                ))
            else:
                self.stdout.write(self.style.SUCCESS(
                    "\nSUCCESS: Demonstration equipment data successfully prepared for the student reservation portal!\n"
                ))

        if apply_mode:
            with transaction.atomic():
                execute_plan()
        else:
            execute_plan()
