# CBA IMS — Frontend Page Coverage Audit

**Updated:** 2026-10-28

**Branch:** `feat/cba-frontend-storefront-staff-polish` (private draft PR #1, unmerged). The baseline `develop` commit was `1894d69` when the frontend branch was created.

## Definitions and important limits

This audit counts **standalone top-level Django HTML templates** in the 12 feature folders, not distinct URLs, user permissions, or reusable partials. It excludes root-level error/shared templates, print styles, and reusable HTML partials. “Patched” means presentation changes are committed on this draft feature branch; it does **not** mean browser-tested, fully redesigned, accessible, or production-ready.

The public Student journey (landing, catalog, reservation form, confirmation, tracking) has a storefront presentation pass across all five standalone pages. The Staff pages below receive consistent, scoped card, header, form, focus, spacing and mobile styling. The Phase 4E2 Custodian files are untouched to protect the user's local uncommitted work.

## Coverage by module

| Module | HTML templates | Patched in draft branch | Not patched |
| --- | ---: | ---: | ---: |
| accounts | 6 | 1 | 5 |
| assignments | 6 | 5 | 1 |
| audit | 1 | 0 | 1 |
| borrowing | 9 | 9 | 0 |
| disposals | 8 | 0 | 8 |
| inventory | 15 | 3 | 12 |
| maintenance | 10 | 5 | 5 |
| organizations | 7 | 0 | 7 |
| reports | 17 | 0 | 17 |
| student_reservations | 8 | 5 | 3 |
| supplies | 8 | 8 | 0 |
| transfers | 4 | 4 | 0 |
| **Total** | **99** | **40** | **59** |

### Student public journey

- ✓ `landing.html`: storefront landing and collection links
- ✓ `catalog.html`: category browsing, schedule picker visuals
- ✓ `reservation_form.html`: checkout progress and form presentation
- ✓ `confirmation.html`: private token presentation and confirmation
- ✓ `lookup.html`: status lookup and returned status styling
- ○ `base_student.html`: shared template remains unchanged; existing navigation retained
- ○ Custodian `custodian_list.html` and `custodian_detail.html`: intentionally deferred to avoid overwriting separate Phase 4E2 work

### Staff areas patched in this branch

- Dashboard and primary inventory list/detail/create-edit
- Borrowing queue, active loans, detail, request, release, return, rejection, archive, and personal borrowings
- Assignments: active/history, create, return, personal accountability
- Maintenance queue, detail, assess, dispatch repair, complete repair
- Supplies: catalog/detail, add/edit, stock in/out, adjustments, low stock and transactions
- Transfers: pending queue, request, detail and history

## Exact template checklist

✓ = presentation patch in draft PR. ○ = no presentation patch in draft PR.

### accounts (6)

✓ `templates/accounts/dashboard.html`; ○ `templates/accounts/landing.html`; ○ `templates/accounts/login.html`; ○ `templates/accounts/password_change.html`; ○ `templates/accounts/user_form.html`; ○ `templates/accounts/user_list.html`

### assignments (6)

✓ `templates/assignments/assignment_confirm_return.html`; ✓ `templates/assignments/assignment_form.html`; ✓ `templates/assignments/assignment_history_list.html`; ✓ `templates/assignments/current_assignment_list.html`; ✓ `templates/assignments/my_accountability.html`; ○ `templates/assignments/printable_accountability.html`

### audit (1)

○ `templates/audit/audit_log_list.html`

### borrowing (9)

✓ `templates/borrowing/borrowing_active_list.html`; ✓ `templates/borrowing/borrowing_detail.html`; ✓ `templates/borrowing/borrowing_form.html`; ✓ `templates/borrowing/borrowing_history_list.html`; ✓ `templates/borrowing/borrowing_list.html`; ✓ `templates/borrowing/borrowing_reject_form.html`; ✓ `templates/borrowing/borrowing_release_form.html`; ✓ `templates/borrowing/borrowing_return_form.html`; ✓ `templates/borrowing/my_borrowings.html`

### disposals (8)

○ `templates/disposals/disposal_approve_form.html`; ○ `templates/disposals/disposal_cancel_form.html`; ○ `templates/disposals/disposal_complete_form.html`; ○ `templates/disposals/disposal_detail.html`; ○ `templates/disposals/disposal_list.html`; ○ `templates/disposals/disposal_print.html`; ○ `templates/disposals/disposal_reject_form.html`; ○ `templates/disposals/disposal_request_form.html`

### inventory (15)

○ `templates/inventory/asset_confirm_delete.html`; ✓ `templates/inventory/asset_detail.html`; ✓ `templates/inventory/asset_form.html`; ✓ `templates/inventory/asset_list.html`; ○ `templates/inventory/asset_qr_label.html`; ○ `templates/inventory/asset_verify_form.html`; ○ `templates/inventory/brand_form.html`; ○ `templates/inventory/brand_list.html`; ○ `templates/inventory/bulk_qr_labels.html`; ○ `templates/inventory/bulk_qr_labels_print.html`; ○ `templates/inventory/category_form.html`; ○ `templates/inventory/category_list.html`; ○ `templates/inventory/physical_verification_list.html`; ○ `templates/inventory/qr_asset_lookup.html`; ○ `templates/inventory/scan_asset.html`

### maintenance (10)

✓ `templates/maintenance/maintenance_assess_form.html`; ○ `templates/maintenance/maintenance_cancel_form.html`; ✓ `templates/maintenance/maintenance_complete_form.html`; ✓ `templates/maintenance/maintenance_detail.html`; ○ `templates/maintenance/maintenance_for_replacement_form.html`; ○ `templates/maintenance/maintenance_history_list.html`; ✓ `templates/maintenance/maintenance_list.html`; ○ `templates/maintenance/maintenance_report_form.html`; ✓ `templates/maintenance/maintenance_start_repair_form.html`; ○ `templates/maintenance/my_maintenance_list.html`

### organizations (7)

○ `templates/organizations/department_form.html`; ○ `templates/organizations/department_list.html`; ○ `templates/organizations/employee_detail.html`; ○ `templates/organizations/employee_form.html`; ○ `templates/organizations/employee_list.html`; ○ `templates/organizations/location_form.html`; ○ `templates/organizations/location_list.html`

### reports (17)

○ `templates/reports/accountability_report.html`; ○ `templates/reports/asset_by_department.html`; ○ `templates/reports/asset_by_location.html`; ○ `templates/reports/asset_inventory_report.html`; ○ `templates/reports/audit_log_report.html`; ○ `templates/reports/borrowing_report.html`; ○ `templates/reports/disposal_report.html`; ○ `templates/reports/employee_accountability_report.html`; ○ `templates/reports/maintenance_cost_summary.html`; ○ `templates/reports/maintenance_report.html`; ○ `templates/reports/report_print.html`; ○ `templates/reports/reports_dashboard.html`; ○ `templates/reports/supply_department_usage.html`; ○ `templates/reports/supply_stock_report.html`; ○ `templates/reports/supply_transactions_report.html`; ○ `templates/reports/transfer_report.html`; ○ `templates/reports/verification_report.html`

### student_reservations (8)

○ `templates/student_reservations/base_student.html`; ✓ `templates/student_reservations/catalog.html`; ✓ `templates/student_reservations/confirmation.html`; ○ `templates/student_reservations/custodian_detail.html`; ○ `templates/student_reservations/custodian_list.html`; ✓ `templates/student_reservations/landing.html`; ✓ `templates/student_reservations/lookup.html`; ✓ `templates/student_reservations/reservation_form.html`

### supplies (8)

✓ `templates/supplies/low_stock_list.html`; ✓ `templates/supplies/stock_adjustment_form.html`; ✓ `templates/supplies/stock_in_form.html`; ✓ `templates/supplies/stock_out_form.html`; ✓ `templates/supplies/supply_detail.html`; ✓ `templates/supplies/supply_form.html`; ✓ `templates/supplies/supply_list.html`; ✓ `templates/supplies/transaction_list.html`

### transfers (4)

✓ `templates/transfers/pending_transfer_list.html`; ✓ `templates/transfers/transfer_detail.html`; ✓ `templates/transfers/transfer_form.html`; ✓ `templates/transfers/transfer_history_list.html`

## Remaining frontend work

1. Keep `develop` and persistent SQLite databases untouched. Finish and integrate Phase 4E2 guard inspection / School ID collection separately before rebasing this draft PR.
2. Verify current draft changes with Django checks and regression suite, then browser screenshots at 390, 768, 1440 widths on a verified disposable database; check Student workflow plus Admin/Faculty/Chair/Dean roles.
3. Review unpatched operational templates: disposals, staff reporting/export, inventory QR/verification, organizations, account management, category/brand lists, specialist maintenance and supply partials.
4. Finish shared shell design/accessibility consistency, printer layouts, keyboard focus, error states and responsive overflow checks. Do not assume “patched” pages are final designs.

## Security and architecture

The feature branch uses Bootstrap 5.3, HTMX and Alpine and adds only scoped CSS and Django template presentation. No server-side view, form, service, model, migration or permission code was edited. Existing CSRF controls, POST actions, search/filter endpoints, role guards and tracking-token logic should remain intact; structural source inspections have verified that controls were not intentionally removed. This is **not** a substitute for runtime tests.

No code from this draft PR should be merged into the canonical branch until Phase 4E2 and this frontend branch are independently regression- and browser-tested.
