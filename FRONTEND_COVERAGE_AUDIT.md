# CBA IMS — Frontend Page Coverage Audit

Updated: 2026-10-28. Draft feature branch: `feat/cba-frontend-storefront-staff-polish` (private GitHub PR #1, **not merged**). Baseline `develop` at `1894d69d36c59601282d7caf54b79543af33c177` when created.

## Scope and interpretation

This audit counts **standalone top-level Django HTML templates** within the 12 feature directories. It does not count reusable partials, shared root templates, error pages, or CSS files. Some files are print layouts or include-only aliases rather than a unique routable screen. A ✓ mark means a scoped frontend presentation patch exists **in the draft branch**, NOT that it has been run, browser-tested, accessibility-reviewed, or approved for production.

The public Student journey has presentation patches across all five standalone screens: home, catalog, request form, confirmation, and tracking. The availability result partial is styled by the catalog's scoped CSS; the reusable public tracking status card is also a modified partial. The Staff Custodian queue and detail pages are deliberately **not modified** because local Phase 4E2 work may still be uncommitted.

## Coverage by feature

| Directory | Top-level HTML | Patched in draft | Remaining |
| --- | ---: | ---: | ---: |
| accounts | 6 | 4 | 2 |
| assignments | 6 | 5 | 1 |
| audit | 1 | 1 | 0 |
| borrowing | 9 | 9 | 0 |
| disposals | 8 | 7 | 1 |
| inventory | 15 | 6 | 9 |
| maintenance | 10 | 5 | 5 |
| organizations | 7 | 7 | 0 |
| reports | 17 | 16 | 1 |
| student_reservations | 8 | 5 | 3 |
| supplies | 8 | 8 | 0 |
| transfers | 4 | 4 | 0 |
| **Total** | **99** | **77** | **22** |

## Patch highlights

- **Student (5)**: storefront landing/catalog, checkout-style request form, success confirmation and tracking/status presentation.
- **Staff operations**: dashboard; borrowing; assignments; supplies; transfers; high-use inventory and maintenance screens.
- **Administration**: asset disposal review and approval screens; organizations directory, employees/departments/locations; user account forms; audit logs; inventory categories, brands and physical verification.
- **Reports (16)**: on-screen reports dashboard, inventory, loan, accountability, audit, disposals, maintenance, supplies and transfers. Print-specific `reports/report_print.html` remains untouched to preserve printed output.

## Exact template checklist

✓ = presentation patch committed on draft branch. ○ = unchanged by this feature branch. Neither symbol is a runtime test result.

### accounts (6)

✓ `templates/accounts/dashboard.html`; ○ `templates/accounts/landing.html`; ○ `templates/accounts/login.html`; ✓ `templates/accounts/password_change.html`; ✓ `templates/accounts/user_form.html`; ✓ `templates/accounts/user_list.html`

### assignments (6)

✓ `templates/assignments/assignment_confirm_return.html`; ✓ `templates/assignments/assignment_form.html`; ✓ `templates/assignments/assignment_history_list.html`; ✓ `templates/assignments/current_assignment_list.html`; ✓ `templates/assignments/my_accountability.html`; ○ `templates/assignments/printable_accountability.html`

### audit (1)

✓ `templates/audit/audit_log_list.html`

### borrowing (9)

✓ `templates/borrowing/borrowing_active_list.html`; ✓ `templates/borrowing/borrowing_detail.html`; ✓ `templates/borrowing/borrowing_form.html`; ✓ `templates/borrowing/borrowing_history_list.html`; ✓ `templates/borrowing/borrowing_list.html`; ✓ `templates/borrowing/borrowing_reject_form.html`; ✓ `templates/borrowing/borrowing_release_form.html`; ✓ `templates/borrowing/borrowing_return_form.html`; ✓ `templates/borrowing/my_borrowings.html`

### disposals (8)

✓ `templates/disposals/disposal_approve_form.html`; ✓ `templates/disposals/disposal_cancel_form.html`; ✓ `templates/disposals/disposal_complete_form.html`; ✓ `templates/disposals/disposal_detail.html`; ✓ `templates/disposals/disposal_list.html`; ○ `templates/disposals/disposal_print.html`; ✓ `templates/disposals/disposal_reject_form.html`; ✓ `templates/disposals/disposal_request_form.html`

### inventory (15)

○ `templates/inventory/asset_confirm_delete.html`; ✓ `templates/inventory/asset_detail.html`; ✓ `templates/inventory/asset_form.html`; ✓ `templates/inventory/asset_list.html`; ○ `templates/inventory/asset_qr_label.html`; ○ `templates/inventory/asset_verify_form.html`; ○ `templates/inventory/brand_form.html`; ✓ `templates/inventory/brand_list.html`; ○ `templates/inventory/bulk_qr_labels.html`; ○ `templates/inventory/bulk_qr_labels_print.html`; ○ `templates/inventory/category_form.html`; ✓ `templates/inventory/category_list.html`; ✓ `templates/inventory/physical_verification_list.html`; ○ `templates/inventory/qr_asset_lookup.html`; ○ `templates/inventory/scan_asset.html`

### maintenance (10)

✓ `templates/maintenance/maintenance_assess_form.html`; ○ `templates/maintenance/maintenance_cancel_form.html`; ✓ `templates/maintenance/maintenance_complete_form.html`; ✓ `templates/maintenance/maintenance_detail.html`; ○ `templates/maintenance/maintenance_for_replacement_form.html`; ○ `templates/maintenance/maintenance_history_list.html`; ✓ `templates/maintenance/maintenance_list.html`; ○ `templates/maintenance/maintenance_report_form.html`; ✓ `templates/maintenance/maintenance_start_repair_form.html`; ○ `templates/maintenance/my_maintenance_list.html`

### organizations (7)

✓ `templates/organizations/department_form.html`; ✓ `templates/organizations/department_list.html`; ✓ `templates/organizations/employee_detail.html`; ✓ `templates/organizations/employee_form.html`; ✓ `templates/organizations/employee_list.html`; ✓ `templates/organizations/location_form.html`; ✓ `templates/organizations/location_list.html`

### reports (17)

✓ `templates/reports/accountability_report.html`; ✓ `templates/reports/asset_by_department.html`; ✓ `templates/reports/asset_by_location.html`; ✓ `templates/reports/asset_inventory_report.html`; ✓ `templates/reports/audit_log_report.html`; ✓ `templates/reports/borrowing_report.html`; ✓ `templates/reports/disposal_report.html`; ✓ `templates/reports/employee_accountability_report.html`; ✓ `templates/reports/maintenance_cost_summary.html`; ✓ `templates/reports/maintenance_report.html`; ○ `templates/reports/report_print.html`; ✓ `templates/reports/reports_dashboard.html`; ✓ `templates/reports/supply_department_usage.html`; ✓ `templates/reports/supply_stock_report.html`; ✓ `templates/reports/supply_transactions_report.html`; ✓ `templates/reports/transfer_report.html`; ✓ `templates/reports/verification_report.html`

### student_reservations (8)

○ `templates/student_reservations/base_student.html`; ✓ `templates/student_reservations/catalog.html`; ✓ `templates/student_reservations/confirmation.html`; ○ `templates/student_reservations/custodian_detail.html`; ○ `templates/student_reservations/custodian_list.html`; ✓ `templates/student_reservations/landing.html`; ✓ `templates/student_reservations/lookup.html`; ✓ `templates/student_reservations/reservation_form.html`

### supplies (8)

✓ `templates/supplies/low_stock_list.html`; ✓ `templates/supplies/stock_adjustment_form.html`; ✓ `templates/supplies/stock_in_form.html`; ✓ `templates/supplies/stock_out_form.html`; ✓ `templates/supplies/supply_detail.html`; ✓ `templates/supplies/supply_form.html`; ✓ `templates/supplies/supply_list.html`; ✓ `templates/supplies/transaction_list.html`

### transfers (4)

✓ `templates/transfers/pending_transfer_list.html`; ✓ `templates/transfers/transfer_detail.html`; ✓ `templates/transfers/transfer_form.html`; ✓ `templates/transfers/transfer_history_list.html`

## Intentionally excluded or still needing work

- Phase 4E2 Custodian templates (`student_reservations/custodian_list.html`, `custodian_detail.html`): avoid overwriting separate local guard inspection / School ID workflow changes.
- Shared Student base template, specialized inventory QR/scan/print screens, certain maintenance and assignment views, login and error/print templates.
- Standalone printable disposal/report templates: require a dedicated print layout acceptance pass rather than general dashboard CSS.
- Remaining reusable partials, navbar/sidebar, keyboard navigation, accessibility, 390/768/1440 responsive overflow checks, and role-specific browser review.

## Merge gate and evidence

**Code-level checks performed:** file-scope diff inspections; Django `if`/`for`/`block` open/close count checks when generating each template; preserving existing form tags, CSRF markers, HTMX/JS action counts; CSS brace balance. These are structural checks, **not actual Django template rendering or browser acceptance**.

**Not yet executed:** `python manage.py check`, full Django regression suite, true browser screenshots, request form submissions or export tests. Those must be run using isolated Django tests and the verified disposable SQLite browser database, never on the protected staff/student/integrated persistent databases. Review semantic status borders, form errors, CSP/static file serving and permissions before merging.

Current feature branch is intended as a reviewable frontend staging branch only. No backend services, models, migrations, authorization, production site, Neon, Vercel or public GitHub repository were modified. Keep PR #1 draft until Phase 4E2 is safely integrated and the frontend has passed complete test and visual review.
