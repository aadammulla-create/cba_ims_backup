# CBA IMS — Frontend Coverage Inventory

Updated: 2026-10-28. Working branch: `feat/cba-frontend-storefront-staff-polish`, draft PR #1 against private `develop`.

**Audit scope:** Django top-level HTML templates under twelve feature directories. Shared top-level templates, reusable partials, error pages, JavaScript and print/PDF styles require separate review. These counts are templates, not a census of distinct routable views or permissions.

## Current frontend changes

- Public Student screens: **5 of 5** standalone pages have a scoped storefront presentation pass (home, catalog, reservation form, confirmation, tracking). Included availability results and status cards inherit their page-specific styling. The shared student base template is unchanged.
- Staff: **7** key standalone templates have a scoped presentation pass (dashboard, asset list/detail/form, active loans/detail, maintenance queue). Other staff pages retain their existing interface and remain on the roadmap.
- These changes are **not yet browser-tested**; they are draft code subject to testing and design review. No server-side access, booking logic, or database changes were made.

## Template inventory (excluding partials)

| Directory | Templates | Touched in feature branch | Untouched |
| --- | ---: | ---: | ---: |
| accounts | 6 | 1 | 5 |
| assignments | 6 | 0 | 6 |
| audit | 1 | 0 | 1 |
| borrowing | 9 | 2 | 7 |
| disposals | 8 | 0 | 8 |
| inventory | 15 | 3 | 12 |
| maintenance | 10 | 1 | 9 |
| organizations | 7 | 0 | 7 |
| reports | 17 | 0 | 17 |
| student_reservations | 8 | 5 | 3 |
| supplies | 8 | 0 | 8 |
| transfers | 4 | 0 | 4 |
| **Total** | **99** | **12** | **87** |

## Exact template checklist

✓ = scoped frontend update in this PR; ○ = no change in this PR. **Neither mark is a statement of test pass or production readiness.**

### accounts (6)

✓ `templates/accounts/dashboard.html`; ○ `templates/accounts/landing.html`; ○ `templates/accounts/login.html`; ○ `templates/accounts/password_change.html`; ○ `templates/accounts/user_form.html`; ○ `templates/accounts/user_list.html`

### assignments (6)

○ `templates/assignments/assignment_confirm_return.html`; ○ `templates/assignments/assignment_form.html`; ○ `templates/assignments/assignment_history_list.html`; ○ `templates/assignments/current_assignment_list.html`; ○ `templates/assignments/my_accountability.html`; ○ `templates/assignments/printable_accountability.html`

### audit (1)

○ `templates/audit/audit_log_list.html`

### borrowing (9)

✓ `templates/borrowing/borrowing_active_list.html`; ✓ `templates/borrowing/borrowing_detail.html`; ○ `templates/borrowing/borrowing_form.html`; ○ `templates/borrowing/borrowing_history_list.html`; ○ `templates/borrowing/borrowing_list.html`; ○ `templates/borrowing/borrowing_reject_form.html`; ○ `templates/borrowing/borrowing_release_form.html`; ○ `templates/borrowing/borrowing_return_form.html`; ○ `templates/borrowing/my_borrowings.html`

### disposals (8)

○ `templates/disposals/disposal_approve_form.html`; ○ `templates/disposals/disposal_cancel_form.html`; ○ `templates/disposals/disposal_complete_form.html`; ○ `templates/disposals/disposal_detail.html`; ○ `templates/disposals/disposal_list.html`; ○ `templates/disposals/disposal_print.html`; ○ `templates/disposals/disposal_reject_form.html`; ○ `templates/disposals/disposal_request_form.html`

### inventory (15)

○ `templates/inventory/asset_confirm_delete.html`; ✓ `templates/inventory/asset_detail.html`; ✓ `templates/inventory/asset_form.html`; ✓ `templates/inventory/asset_list.html`; ○ `templates/inventory/asset_qr_label.html`; ○ `templates/inventory/asset_verify_form.html`; ○ `templates/inventory/brand_form.html`; ○ `templates/inventory/brand_list.html`; ○ `templates/inventory/bulk_qr_labels.html`; ○ `templates/inventory/bulk_qr_labels_print.html`; ○ `templates/inventory/category_form.html`; ○ `templates/inventory/category_list.html`; ○ `templates/inventory/physical_verification_list.html`; ○ `templates/inventory/qr_asset_lookup.html`; ○ `templates/inventory/scan_asset.html`

### maintenance (10)

○ `templates/maintenance/maintenance_assess_form.html`; ○ `templates/maintenance/maintenance_cancel_form.html`; ○ `templates/maintenance/maintenance_complete_form.html`; ○ `templates/maintenance/maintenance_detail.html`; ○ `templates/maintenance/maintenance_for_replacement_form.html`; ○ `templates/maintenance/maintenance_history_list.html`; ✓ `templates/maintenance/maintenance_list.html`; ○ `templates/maintenance/maintenance_report_form.html`; ○ `templates/maintenance/maintenance_start_repair_form.html`; ○ `templates/maintenance/my_maintenance_list.html`

### organizations (7)

○ `templates/organizations/department_form.html`; ○ `templates/organizations/department_list.html`; ○ `templates/organizations/employee_detail.html`; ○ `templates/organizations/employee_form.html`; ○ `templates/organizations/employee_list.html`; ○ `templates/organizations/location_form.html`; ○ `templates/organizations/location_list.html`

### reports (17)

○ `templates/reports/accountability_report.html`; ○ `templates/reports/asset_by_department.html`; ○ `templates/reports/asset_by_location.html`; ○ `templates/reports/asset_inventory_report.html`; ○ `templates/reports/audit_log_report.html`; ○ `templates/reports/borrowing_report.html`; ○ `templates/reports/disposal_report.html`; ○ `templates/reports/employee_accountability_report.html`; ○ `templates/reports/maintenance_cost_summary.html`; ○ `templates/reports/maintenance_report.html`; ○ `templates/reports/report_print.html`; ○ `templates/reports/reports_dashboard.html`; ○ `templates/reports/supply_department_usage.html`; ○ `templates/reports/supply_stock_report.html`; ○ `templates/reports/supply_transactions_report.html`; ○ `templates/reports/transfer_report.html`; ○ `templates/reports/verification_report.html`

### student_reservations (8)

○ `templates/student_reservations/base_student.html`; ✓ `templates/student_reservations/catalog.html`; ✓ `templates/student_reservations/confirmation.html`; ○ `templates/student_reservations/custodian_detail.html`; ○ `templates/student_reservations/custodian_list.html`; ✓ `templates/student_reservations/landing.html`; ✓ `templates/student_reservations/lookup.html`; ✓ `templates/student_reservations/reservation_form.html`

### supplies (8)

○ `templates/supplies/low_stock_list.html`; ○ `templates/supplies/stock_adjustment_form.html`; ○ `templates/supplies/stock_in_form.html`; ○ `templates/supplies/stock_out_form.html`; ○ `templates/supplies/supply_detail.html`; ○ `templates/supplies/supply_form.html`; ○ `templates/supplies/supply_list.html`; ○ `templates/supplies/transaction_list.html`

### transfers (4)

○ `templates/transfers/pending_transfer_list.html`; ○ `templates/transfers/transfer_detail.html`; ○ `templates/transfers/transfer_form.html`; ○ `templates/transfers/transfer_history_list.html`

## Prioritized remainder

1. Protect and integrate the separate Phase 4E2 guard inspection and School ID collection work. The `student_reservations/custodian_detail.html` and `custodian_list.html` templates are intentionally untouched by this frontend branch.
2. Verify present draft frontend changes on disposable SQLite: Django checks, full tests, screenshots at 390px/768px/1440px, Student booking and tracking, Staff roles and navigation.
3. Staff operational processes: assignment forms, borrowing request/release/return screens, maintenance assessment and repair, transfers, disposals, supplies and category/brand management.
4. Reporting, administrative, QR, audit, employee/accountability, and print templates; mobile/accessibility review by role.
5. End-to-end visual consistency; test responsive overflow and keyboard interaction before merge.

## Engineering constraints

Preserve the current Django architecture, Bootstrap 5.3/HTMX/Alpine, no React/Tailwind or frontend build system. No database writes, migrations, backend edits, permission edits, public GitHub changes or pushes to `develop` until explicit approval. Current CSS is loaded per page to avoid unexpected global effects. No screenshot or automated Django regression test has been executed from this remote GitHub-only implementation environment.
