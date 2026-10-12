import os
import sys
import subprocess
from datetime import timedelta
from decimal import Decimal

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.conf import settings
from django.core.management import call_command
from django.test.utils import setup_test_environment, teardown_test_environment

# Use test runner database setup for safe isolation
from django.test.runner import DiscoverRunner
runner = DiscoverRunner(verbosity=0)
old_config = runner.setup_databases()
setup_test_environment()

from django.test import Client
from django.urls import reverse
from django.utils import timezone
from django.db import connection

from apps.accounts.models import User
from apps.organizations.models import Department, Location, Employee
from apps.inventory.models import Asset, AssetCategory, Brand, EquipmentType
from apps.student_reservations.models import StudentReservation
from apps.borrowing.models import AssetBorrowing
from apps.maintenance.models import AssetMaintenance
from apps.transfers.models import AssetTransfer
from apps.supplies.models import Supply, SupplyCategory, SupplyTransaction
from apps.audit.models import AuditLog


def render_pages():
    now = timezone.now()

    # 1. Setup synthetic data
    dept = Department.objects.create(name='College of Business Administration', code='CBA')
    loc = Location.objects.create(name='Main Property Office', building='CBA Hall', room_number='101', department=dept)
    loc_lab = Location.objects.create(name='Computer Laboratory 1', building='CBA Hall', room_number='201', department=dept)

    admin = User.objects.create_superuser('admin_qa', 'admin@cba.edu', 'Pass1234!', role=User.Role.ADMIN, first_name='Juan', last_name='Dela Cruz')
    faculty = User.objects.create_user('faculty_qa', 'faculty@cba.edu', 'Pass1234!', role=User.Role.FACULTY, first_name='Maria', last_name='Santos')
    emp_fac = Employee.objects.create(user=faculty, employee_id='EMP-CBA-01', first_name='Maria', last_name='Santos', department=dept, location=loc)

    cat_comp = AssetCategory.objects.create(name='Computer Equipment', code='CMP', is_active=True, is_reservable=True)
    cat_av = AssetCategory.objects.create(name='Audio-Visual', code='AV', is_active=True, is_reservable=True)
    brand_dell = Brand.objects.create(name='Dell', is_active=True)
    brand_epson = Brand.objects.create(name='Epson', is_active=True)

    # Assets
    a1 = Asset.objects.create(item_name='Dell Latitude 5420', asset_code='CBA-CMP-00001', category=cat_comp, brand=brand_dell, department=dept, current_location=loc, condition=Asset.Condition.GOOD, status=Asset.Status.AVAILABLE, acquisition_cost=Decimal('45000.00'), created_by=admin)
    a2 = Asset.objects.create(item_name='Epson EB-E01 Projector', asset_code='CBA-AV-00002', category=cat_av, brand=brand_epson, department=dept, current_location=loc, condition=Asset.Condition.GOOD, status=Asset.Status.AVAILABLE, acquisition_cost=Decimal('28000.00'), created_by=admin)
    a3 = Asset.objects.create(item_name='ThinkPad E14 Gen 2', asset_code='CBA-CMP-00003', category=cat_comp, brand=brand_dell, department=dept, current_location=loc_lab, condition=Asset.Condition.GOOD, status=Asset.Status.ASSIGNED, acquisition_cost=Decimal('42000.00'), created_by=admin)
    a4 = Asset.objects.create(item_name='Sony Wireless Presenter', asset_code='CBA-AV-00004', category=cat_av, brand=brand_epson, department=dept, current_location=loc, condition=Asset.Condition.GOOD, status=Asset.Status.BORROWED, acquisition_cost=Decimal('5000.00'), created_by=admin)
    a5 = Asset.objects.create(item_name='Canon imageRUNNER Copier', asset_code='CBA-CMP-00005', category=cat_comp, brand=brand_dell, department=dept, current_location=loc, condition=Asset.Condition.POOR, status=Asset.Status.MAINTENANCE, acquisition_cost=Decimal('85000.00'), created_by=admin)
    a6 = Asset.objects.create(item_name='Acer TravelMate P2', asset_code='CBA-CMP-00006', category=cat_comp, brand=brand_dell, department=dept, current_location=loc, condition=Asset.Condition.UNSERVICEABLE, status=Asset.Status.DAMAGED, acquisition_cost=Decimal('32000.00'), created_by=admin)

    # 1. Pending Student Reservation
    res_pending = StudentReservation.objects.create(
        student_id='2024-00123',
        student_name='Clara Ramos',
        course_year_section='BSBA 3-A',
        email='c.ramos@student.cba.edu',
        contact_number='09171234567',
        category=cat_av,
        requested_pickup=now + timedelta(hours=2),
        requested_return=now + timedelta(hours=5),
        purpose='Financial Management Feasibility Presentation',
        status=StudentReservation.Status.PENDING
    )

    # 2. Guard Return Awaiting Inspection
    res_guard = StudentReservation.objects.create(
        student_id='2024-00456',
        student_name='Joshua Dizon',
        course_year_section='BSBA 4-B',
        email='j.dizon@student.cba.edu',
        contact_number='09187654321',
        category=cat_comp,
        asset=a1,
        requested_pickup=now - timedelta(hours=5),
        requested_return=now - timedelta(hours=1),
        purpose='Senior Thesis Capstone Defense',
        status=StudentReservation.Status.RETURNED_TO_GUARD,
        guard_returned_at=now - timedelta(minutes=45),
        guard_recorded_by=admin
    )

    # 3. Overdue Borrowing
    AssetBorrowing.objects.create(
        asset=a4,
        borrower=emp_fac,
        borrower_department=dept,
        purpose='Department Accreditation Review',
        requested_start=now - timedelta(hours=8),
        requested_return=now - timedelta(hours=2),
        status=AssetBorrowing.Status.RELEASED,
        released_by=admin
    )

    # 4. Open Maintenance Case
    AssetMaintenance.objects.create(
        asset=a5,
        issue_title='Drum Roller Defect & Paper Feed Jam',
        issue_description='Copier continuously jams during bulk exam printing. Error E000-0001 displayed on panel.',
        reported_by=admin,
        status=AssetMaintenance.Status.REPORTED,
        severity=AssetMaintenance.Severity.CRITICAL
    )

    # 5. Pending Transfer
    dept_acct = Department.objects.create(name='Department of Accountancy', code='ACCT')
    AssetTransfer.objects.create(
        asset=a3,
        from_department=dept,
        to_department=dept_acct,
        reason='Faculty reassignment for 2nd Semester',
        status=AssetTransfer.Status.PENDING,
        requested_by=admin
    )

    # 6. Low stock supply
    scat = SupplyCategory.objects.create(name='Paper & Office Supplies', code='OFC')
    supply = Supply.objects.create(item_name='Multipurpose Copy Paper A4 (70gsm)', category=scat, reorder_level=20, unit=Supply.Unit.REAM)
    SupplyTransaction.objects.create(supply=supply, transaction_type=SupplyTransaction.TransactionType.STOCK_IN, quantity=12, processed_by=admin)

    # 7. Audit log entries
    AuditLog.objects.create(user=admin, action='ASSET_UPDATED', model_name='Asset', object_id=str(a1.id), object_repr='Dell Latitude 5420 (CBA-CMP-00001)', changes={'status': 'AVAILABLE'})
    AuditLog.objects.create(user=admin, action='STUDENT_RESERVATION_RETURNED_GUARD', model_name='StudentReservation', object_id=str(res_guard.id), object_repr='Joshua Dizon - Dell Latitude 5420', changes={'status': 'RETURNED_TO_GUARD'})
    AuditLog.objects.create(user=admin, action='MAINTENANCE_REPORTED', model_name='AssetMaintenance', object_id='1', object_repr='Canon imageRUNNER Copier', changes={'severity': 'CRITICAL'})

    # Render Active Dashboard via Test Client
    client = Client()
    client.force_login(admin)
    resp = client.get(reverse('dashboard'))
    content = resp.content.decode('utf-8')

    # Fix relative static URLs to absolute file URLs for offline headless rendering
    base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    custom_css_path = f"file:///{base_dir.replace(os.sep, '/')}/static/css/custom.css"
    content = content.replace('/static/css/custom.css?v=3.1', custom_css_path)
    content = content.replace('/static/css/custom.css', custom_css_path)
    content = content.replace('/static/vendor/htmx/htmx.min.js', f"file:///{base_dir.replace(os.sep, '/')}/static/vendor/htmx/htmx.min.js")
    content = content.replace('/static/vendor/alpine/alpine.min.js', f"file:///{base_dir.replace(os.sep, '/')}/static/vendor/alpine/alpine.min.js")

    output_dir = os.path.join(base_dir, 'docs', 'visual-qa')
    os.makedirs(output_dir, exist_ok=True)

    active_html_path = os.path.join(output_dir, 'dashboard_active_preview.html')
    with open(active_html_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"Active dashboard HTML written to {active_html_path}")

    # Render Empty State Dashboard
    # Clear queues
    StudentReservation.objects.all().delete()
    AssetBorrowing.objects.all().delete()
    AssetMaintenance.objects.all().delete()
    AssetTransfer.objects.all().delete()
    SupplyTransaction.objects.all().delete()
    Supply.objects.all().delete()

    resp_empty = client.get(reverse('dashboard'))
    content_empty = resp_empty.content.decode('utf-8')
    content_empty = content_empty.replace('/static/css/custom.css?v=3.1', custom_css_path)
    content_empty = content_empty.replace('/static/css/custom.css', custom_css_path)
    content_empty = content_empty.replace('/static/vendor/htmx/htmx.min.js', f"file:///{base_dir.replace(os.sep, '/')}/static/vendor/htmx/htmx.min.js")
    content_empty = content_empty.replace('/static/vendor/alpine/alpine.min.js', f"file:///{base_dir.replace(os.sep, '/')}/static/vendor/alpine/alpine.min.js")

    empty_html_path = os.path.join(output_dir, 'dashboard_empty_preview.html')
    with open(empty_html_path, 'w', encoding='utf-8') as f:
        f.write(content_empty)

    print(f"Empty dashboard HTML written to {empty_html_path}")
    return active_html_path, empty_html_path


def capture_screenshots(active_html, empty_html):
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    output_dir = os.path.join(base_dir, 'docs', 'visual-qa')

    shots = [
        # Desktop 1440px
        (active_html, 'dashboard-desktop-1440.png', 1440, 1100),
        # Tablet 768px
        (active_html, 'dashboard-tablet-768.png', 768, 1024),
        # Mobile 390px
        (active_html, 'dashboard-mobile-390.png', 390, 844),
        # Navigation expanded / sidebar desktop
        (active_html, 'dashboard-navigation-expanded.png', 1440, 900),
        # Empty state desktop
        (empty_html, 'dashboard-empty-state-desktop.png', 1440, 1000),
    ]

    for html_file, out_name, width, height in shots:
        out_path = os.path.join(output_dir, out_name)
        file_url = f"file:///{html_file.replace(os.sep, '/')}"
        cmd = [
            chrome_path,
            '--headless=new',
            '--disable-gpu',
            '--no-sandbox',
            f'--window-size={width},{height}',
            f'--screenshot={out_path}',
            file_url
        ]
        print(f"Capturing {out_name} ({width}x{height})...")
        res = subprocess.run(cmd, capture_output=True, text=True)
        if os.path.exists(out_path):
            print(f"Saved: {out_path} ({os.path.getsize(out_path)} bytes)")
        else:
            print(f"Failed to generate {out_name}: {res.stderr}")


if __name__ == '__main__':
    active_html, empty_html = render_pages()
    capture_screenshots(active_html, empty_html)
