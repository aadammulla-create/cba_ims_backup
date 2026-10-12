from django.contrib.auth import views as auth_views
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, View
from django.contrib import messages
from django.db.models import Q, Count
from django.utils import timezone

from .models import User
from .forms import LoginForm, UserCreateForm, UserUpdateForm, PasswordChangeForm


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin that requires the user to be an administrator."""
    def test_func(self):
        return self.request.user.is_admin


class DashboardView(LoginRequiredMixin, TemplateView):
    """Main dashboard view showing system overview."""
    template_name = 'accounts/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Dashboard'

        user = self.request.user
        role = getattr(user, 'role', '')
        is_custodian = getattr(user, 'is_admin', False) or role == User.Role.ADMIN

        chair_dept = None
        if role == User.Role.DEPT_CHAIR:
            chair_dept = getattr(getattr(user, 'employee_profile', None), 'department', None)

        now = timezone.now()

        # Initialize safe default context
        context.update({
            'is_custodian': is_custodian,
            # A. Asset Overview
            'total_assets': 0,
            'available_assets': 0,
            'unserviceable_assets': 0,
            'assigned_assets': 0,
            'borrowed_assets': 0,
            'maintenance_assets': 0,
            'damaged_assets': 0,
            'student_active_loans_count': 0,
            'total_on_loan_assets': 0,
            'total_physical_on_loan': 0,

            # B. Requires Attention Operational Queues
            'pending_reservations_count': 0,
            'pending_reservations_list': [],
            'guard_returns_count': 0,
            'guard_returns_list': [],
            'overdue_loans_count': 0,
            'overdue_loans_list': [],
            'overdue_borrowings_count': 0,
            'pending_borrowings_count': 0,
            'active_borrowings_count': 0,
            'open_maintenance_count': 0,
            'critical_maintenance_count': 0,
            'open_maintenance_list': [],
            'pending_transfers_count': 0,
            'pending_transfers_list': [],
            'low_stock_supplies_count': 0,
            'out_of_stock_supplies_count': 0,
            'low_stock_supplies_list': [],
            'pending_disposals_count': 0,
            'disposed_assets_count': 0,

            # Master Directory metrics
            'total_employees': 0,
            'total_departments': 0,
            'total_locations': 0,
            'total_categories': 0,
            'total_brands': 0,

            # C. Recent Activity
            'recent_activities': [],

            # D. Analytics & Charts
            'category_chart_labels': [],
            'category_chart_data': [],
            'condition_chart_labels': [],
            'condition_chart_data': [],
            'department_chart_labels': [],
            'department_chart_data': [],
            'department_chart_title': "Assets Distribution",
        })

        try:
            from apps.inventory.models import Asset, AssetCategory, Brand
            from apps.organizations.models import Department, Location, Employee
            from apps.audit.models import AuditLog
            from apps.transfers.models import AssetTransfer
            from apps.borrowing.models import AssetBorrowing
            from apps.student_reservations.models import StudentReservation
            from apps.student_reservations.security import mask_contact_info
            from apps.maintenance.models import AssetMaintenance
            from apps.disposals.models import AssetDisposal
            from apps.supplies.models import Supply
            from apps.supplies import services as supply_services

            def _mask_reservation(res):
                if not is_custodian:
                    m_email, m_phone = mask_contact_info(res.email, res.contact_number)
                    res.email = m_email
                    res.contact_number = m_phone
                    res.masked_email = m_email
                    res.masked_phone = m_phone
                else:
                    m_email, m_phone = mask_contact_info(res.email, res.contact_number)
                    res.masked_email = m_email
                    res.masked_phone = m_phone
                return res

            # ---------------------------------------------------------
            # A. ASSET OVERVIEW
            # ---------------------------------------------------------
            asset_qs = Asset.objects.all()
            if chair_dept:
                asset_qs = asset_qs.filter(department=chair_dept)

            total_assets = asset_qs.count()
            available_assets = asset_qs.filter(
                status=Asset.Status.AVAILABLE
            ).exclude(condition=Asset.Condition.UNSERVICEABLE).count()
            unserviceable_assets = asset_qs.filter(condition=Asset.Condition.UNSERVICEABLE).count()
            assigned_assets = asset_qs.filter(status=Asset.Status.ASSIGNED).count()
            borrowed_assets = asset_qs.filter(status=Asset.Status.BORROWED).count()
            maintenance_assets = asset_qs.filter(status=Asset.Status.MAINTENANCE).count()
            damaged_assets = asset_qs.filter(status=Asset.Status.DAMAGED).count()

            # Active Student Loans currently released
            student_active_qs = StudentReservation.objects.filter(
                status=StudentReservation.Status.RELEASED
            )
            if chair_dept:
                student_active_qs = student_active_qs.filter(asset__department=chair_dept)
            elif role == User.Role.FACULTY:
                student_active_qs = StudentReservation.objects.none()

            student_active_loans_count = student_active_qs.count()
            total_on_loan = borrowed_assets + student_active_loans_count

            context['total_assets'] = total_assets
            context['available_assets'] = available_assets
            context['unserviceable_assets'] = unserviceable_assets
            context['assigned_assets'] = assigned_assets
            context['borrowed_assets'] = borrowed_assets
            context['maintenance_assets'] = maintenance_assets
            context['damaged_assets'] = damaged_assets
            context['student_active_loans_count'] = student_active_loans_count
            context['total_on_loan_assets'] = total_on_loan
            context['total_physical_on_loan'] = total_on_loan

            # ---------------------------------------------------------
            # B. REQUIRES ATTENTION OPERATIONAL QUEUES
            # ---------------------------------------------------------
            # 1. Pending Student Reservations (Actionable queue strictly for authorized custodians)
            if is_custodian:
                pending_res_qs = StudentReservation.objects.filter(
                    status=StudentReservation.Status.PENDING
                )
                if chair_dept:
                    pending_res_qs = pending_res_qs.filter(
                        Q(asset__department=chair_dept) | Q(asset__isnull=True)
                    )
                context['pending_reservations_count'] = pending_res_qs.count()
                pending_res_slice = list(
                    pending_res_qs.select_related(
                        'category', 'equipment_type_ref', 'asset', 'asset__department'
                    ).order_by('requested_pickup', 'created_at')[:5]
                )
                for r in pending_res_slice:
                    try:
                        r.detail_url = reverse('student_reservations:custodian_detail', kwargs={'pk': r.pk})
                    except Exception:
                        r.detail_url = ''
                context['pending_reservations_list'] = [_mask_reservation(r) for r in pending_res_slice]
            else:
                context['pending_reservations_count'] = 0
                context['pending_reservations_list'] = []

            # 2. Guard Returns (Actionable queue strictly for authorized custodians)
            if is_custodian:
                guard_returns_qs = StudentReservation.objects.filter(
                    status=StudentReservation.Status.RETURNED_TO_GUARD
                )
                if chair_dept:
                    guard_returns_qs = guard_returns_qs.filter(asset__department=chair_dept)
                context['guard_returns_count'] = guard_returns_qs.count()
                guard_returns_slice = list(
                    guard_returns_qs.select_related(
                        'category', 'equipment_type_ref', 'asset', 'asset__department', 'guard_recorded_by'
                    ).order_by('-guard_returned_at', '-created_at')[:5]
                )
                for g in guard_returns_slice:
                    try:
                        g.detail_url = reverse('student_reservations:custodian_detail', kwargs={'pk': g.pk})
                    except Exception:
                        g.detail_url = ''
                context['guard_returns_list'] = [_mask_reservation(g) for g in guard_returns_slice]
            else:
                context['guard_returns_count'] = 0
                context['guard_returns_list'] = []

            # 3. Overdue Loans (Faculty borrowings + Student reservations for custodians)
            borrowing_overdue_qs = AssetBorrowing.objects.filter(
                Q(status=AssetBorrowing.Status.OVERDUE) |
                Q(status=AssetBorrowing.Status.RELEASED, requested_return__lt=now)
            )
            if chair_dept:
                borrowing_overdue_qs = borrowing_overdue_qs.filter(
                    Q(borrower_department=chair_dept) | Q(asset__department=chair_dept)
                )
            elif role == User.Role.FACULTY:
                borrowing_overdue_qs = borrowing_overdue_qs.filter(borrower__user=user)

            faculty_overdue_count = borrowing_overdue_qs.count()

            # Overdue student loans are only actionable and linkable for custodians
            if is_custodian:
                student_overdue_qs = StudentReservation.objects.filter(
                    status=StudentReservation.Status.RELEASED,
                    requested_return__lt=now
                )
                if chair_dept:
                    student_overdue_qs = student_overdue_qs.filter(asset__department=chair_dept)
                student_overdue_count = student_overdue_qs.count()
            else:
                student_overdue_qs = StudentReservation.objects.none()
                student_overdue_count = 0

            overdue_loans_count = faculty_overdue_count + student_overdue_count
            context['overdue_loans_count'] = overdue_loans_count
            context['overdue_borrowings_count'] = overdue_loans_count

            # Overdue loans list slice
            overdue_borrowing_slice = list(
                borrowing_overdue_qs.select_related(
                    'asset', 'asset__category', 'asset__department', 'borrower', 'borrower__department'
                ).order_by('requested_return')[:5]
            )
            for b in overdue_borrowing_slice:
                b.loan_type = 'FACULTY'
                b.item_type = 'Faculty Loan'
                b.borrower_name = b.borrower.full_name
                b.borrower_id = b.borrower.employee_id
                b.overdue_duration = now - b.requested_return if now > b.requested_return else timezone.timedelta(0)
                try:
                    b.loan_url = reverse('borrowing:borrowing_detail', kwargs={'pk': b.pk})
                except Exception:
                    b.loan_url = ''

            if is_custodian:
                overdue_student_slice = list(
                    student_overdue_qs.select_related(
                        'asset', 'asset__category', 'asset__department', 'category', 'equipment_type_ref'
                    ).order_by('requested_return')[:5]
                )
                for s in overdue_student_slice:
                    s.loan_type = 'STUDENT'
                    s.item_type = 'Student Reservation'
                    s.borrower_name = s.student_name
                    s.borrower_id = s.student_id
                    try:
                        s.loan_url = reverse('student_reservations:custodian_detail', kwargs={'pk': s.pk})
                    except Exception:
                        s.loan_url = ''
                    _mask_reservation(s)
            else:
                overdue_student_slice = []

            combined_overdue = sorted(
                overdue_borrowing_slice + overdue_student_slice,
                key=lambda x: x.requested_return
            )[:5]
            context['overdue_loans_list'] = combined_overdue

            # Maintain active and pending faculty borrowing counts
            pending_borrowings_qs = AssetBorrowing.objects.filter(
                status=AssetBorrowing.Status.PENDING
            )
            active_borrowings_qs = AssetBorrowing.objects.filter(
                status__in=[AssetBorrowing.Status.RELEASED, AssetBorrowing.Status.OVERDUE]
            )
            if chair_dept:
                pending_borrowings_qs = pending_borrowings_qs.filter(
                    Q(borrower_department=chair_dept) | Q(asset__department=chair_dept)
                )
                active_borrowings_qs = active_borrowings_qs.filter(
                    Q(borrower_department=chair_dept) | Q(asset__department=chair_dept)
                )
            elif role == User.Role.FACULTY:
                pending_borrowings_qs = pending_borrowings_qs.filter(borrower__user=user)
                active_borrowings_qs = active_borrowings_qs.filter(borrower__user=user)

            context['pending_borrowings_count'] = pending_borrowings_qs.count()
            context['active_borrowings_count'] = active_borrowings_qs.count()

            # 4. Open Maintenance (Cases requiring staff action: REPORTED, ASSESSED)
            open_maintenance_qs = AssetMaintenance.objects.filter(
                status__in=[
                    AssetMaintenance.Status.REPORTED,
                    AssetMaintenance.Status.ASSESSED
                ]
            )
            critical_maintenance_qs = AssetMaintenance.objects.filter(
                status__in=[
                    AssetMaintenance.Status.REPORTED,
                    AssetMaintenance.Status.ASSESSED,
                    AssetMaintenance.Status.IN_REPAIR
                ],
                severity=AssetMaintenance.Severity.CRITICAL
            )
            if chair_dept:
                open_maintenance_qs = open_maintenance_qs.filter(asset__department=chair_dept)
                critical_maintenance_qs = critical_maintenance_qs.filter(asset__department=chair_dept)
            elif role == User.Role.FACULTY:
                open_maintenance_qs = open_maintenance_qs.filter(reported_by=user)
                critical_maintenance_qs = critical_maintenance_qs.filter(reported_by=user)

            context['open_maintenance_count'] = open_maintenance_qs.count()
            context['critical_maintenance_count'] = critical_maintenance_qs.count()
            open_maintenance_slice = list(
                open_maintenance_qs.select_related(
                    'asset', 'asset__category', 'asset__department', 'reported_by'
                ).order_by('-reported_at')[:5]
            )
            for m in open_maintenance_slice:
                try:
                    m.detail_url = reverse('maintenance:maintenance_detail', kwargs={'pk': m.pk})
                except Exception:
                    m.detail_url = ''
            context['open_maintenance_list'] = open_maintenance_slice

            # 5. Pending Transfers
            transfers_qs = AssetTransfer.objects.filter(
                status__in=[AssetTransfer.Status.PENDING, AssetTransfer.Status.APPROVED]
            )
            if chair_dept:
                transfers_qs = transfers_qs.filter(
                    Q(from_department=chair_dept) | Q(to_department=chair_dept)
                )
            elif role == User.Role.FACULTY:
                transfers_qs = AssetTransfer.objects.none()

            context['pending_transfers_count'] = transfers_qs.count()
            pending_transfers_slice = list(
                transfers_qs.select_related(
                    'asset', 'from_department', 'to_department', 'requested_by'
                ).order_by('-transfer_date', '-id')[:5]
            )
            for t in pending_transfers_slice:
                try:
                    t.detail_url = reverse('transfers:transfer_detail', kwargs={'pk': t.pk})
                except Exception:
                    t.detail_url = ''
            context['pending_transfers_list'] = pending_transfers_slice

            # 6. Consumables & Supplies
            low_supplies = supply_services.get_low_stock_supplies()
            context['low_stock_supplies_count'] = len(low_supplies)
            context['out_of_stock_supplies_count'] = sum(1 for s in low_supplies if s.calculated_stock <= 0)
            context['low_stock_supplies_list'] = low_supplies[:5]

            # 7. Disposals
            context['disposed_assets_count'] = asset_qs.filter(status=Asset.Status.DISPOSED).count()
            disposal_qs = AssetDisposal.objects.filter(
                status__in=[AssetDisposal.Status.PENDING, AssetDisposal.Status.APPROVED]
            )
            if chair_dept:
                disposal_qs = disposal_qs.filter(asset__department=chair_dept)
            elif role == User.Role.FACULTY:
                disposal_qs = AssetDisposal.objects.none()
            context['pending_disposals_count'] = disposal_qs.count()

            # ---------------------------------------------------------
            # C. RECENT ACTIVITY
            # ---------------------------------------------------------
            context['recent_activities'] = list(AuditLog.objects.select_related('user')[:7])

            # ---------------------------------------------------------
            # D. DISTRIBUTION / ANALYTICS CHARTS (Optimized, Non-Faculty)
            # ---------------------------------------------------------
            if role != User.Role.FACULTY:
                # 1. Assets by Category
                cat_counts = (
                    asset_qs.exclude(status=Asset.Status.DISPOSED)
                    .values('category__name')
                    .annotate(count=Count('id'))
                    .order_by('-count')[:6]
                )
                context['category_chart_labels'] = [c['category__name'] or 'Uncategorized' for c in cat_counts]
                context['category_chart_data'] = [c['count'] for c in cat_counts]

                # 2. Assets by Condition
                cond_counts = (
                    asset_qs.exclude(status=Asset.Status.DISPOSED)
                    .values('condition')
                    .annotate(count=Count('id'))
                )
                cond_dict = {c['condition']: c['count'] for c in cond_counts}
                context['condition_chart_labels'] = ['New', 'Good', 'Fair', 'Poor', 'Unserviceable']
                context['condition_chart_data'] = [
                    cond_dict.get(Asset.Condition.NEW, 0),
                    cond_dict.get(Asset.Condition.GOOD, 0),
                    cond_dict.get(Asset.Condition.FAIR, 0),
                    cond_dict.get(Asset.Condition.POOR, 0),
                    cond_dict.get(Asset.Condition.UNSERVICEABLE, 0),
                ]

                # 3. Department or Location Distribution
                if not chair_dept:
                    dept_counts = (
                        Asset.objects.exclude(status=Asset.Status.DISPOSED)
                        .values('department__name')
                        .annotate(count=Count('id'))
                        .order_by('-count')[:6]
                    )
                    context['department_chart_labels'] = [d['department__name'] or 'Unassigned' for d in dept_counts]
                    context['department_chart_data'] = [d['count'] for d in dept_counts]
                    context['department_chart_title'] = "Assets by Department"
                else:
                    loc_counts = (
                        asset_qs.exclude(status=Asset.Status.DISPOSED)
                        .values('current_location__name')
                        .annotate(count=Count('id'))
                        .order_by('-count')[:6]
                    )
                    context['department_chart_labels'] = [l['current_location__name'] or 'Unassigned' for l in loc_counts]
                    context['department_chart_data'] = [l['count'] for l in loc_counts]
                    context['department_chart_title'] = f"Assets by Location ({chair_dept.name})"

            # ---------------------------------------------------------
            # MASTER DIRECTORY METRICS
            # ---------------------------------------------------------
            context['total_employees'] = Employee.objects.filter(is_active=True).count()
            context['total_departments'] = Department.objects.filter(is_active=True).count()
            context['total_locations'] = Location.objects.filter(is_active=True).count()
            context['total_categories'] = AssetCategory.objects.filter(is_active=True).count()
            context['total_brands'] = Brand.objects.filter(is_active=True).count()

        except Exception as e:
            import logging
            logging.getLogger(__name__).exception("Error populating staff dashboard context: %s", e)

        return context


class LoginView(auth_views.LoginView):
    """Custom login view with Bootstrap-styled form."""
    form_class = LoginForm
    template_name = 'accounts/login.html'
    redirect_authenticated_user = True


class LogoutView(auth_views.LogoutView):
    """Logout view that redirects to login page."""
    next_page = '/accounts/login/'


class PasswordChangeView(auth_views.PasswordChangeView):
    """Password change view for authenticated users."""
    form_class = PasswordChangeForm
    template_name = 'accounts/password_change.html'
    success_url = reverse_lazy('dashboard')

    def form_valid(self, form):
        messages.success(self.request, 'Your password was successfully updated!')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Change Password'
        return context


class UserListView(AdminRequiredMixin, ListView):
    """List all users with search and role filtering (admin only)."""
    model = User
    template_name = 'accounts/user_list.html'
    context_object_name = 'users'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.GET.get('q')
        role = self.request.GET.get('role')
        if query:
            queryset = queryset.filter(
                Q(username__icontains=query) |
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query) |
                Q(email__icontains=query)
            )
        if role:
            queryset = queryset.filter(role=role)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['roles'] = User.Role.choices
        context['page_title'] = 'User Management'
        return context


class UserCreateView(AdminRequiredMixin, CreateView):
    """Create a new user (admin only)."""
    model = User
    form_class = UserCreateForm
    template_name = 'accounts/user_form.html'
    success_url = reverse_lazy('accounts:user_list')

    def form_valid(self, form):
        messages.success(self.request, f"User '{form.cleaned_data['username']}' created successfully.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Create User'
        return context


class UserUpdateView(AdminRequiredMixin, UpdateView):
    """Update an existing user (admin only)."""
    model = User
    form_class = UserUpdateForm
    template_name = 'accounts/user_form.html'
    success_url = reverse_lazy('accounts:user_list')

    def form_valid(self, form):
        messages.success(self.request, f"User '{form.cleaned_data['username']}' updated successfully.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Edit User'
        return context


class UserToggleActiveView(AdminRequiredMixin, View):
    """Toggle user active status (admin only, POST only)."""
    def post(self, request, pk, *args, **kwargs):
        user = get_object_or_404(User, pk=pk)
        if user == request.user:
            messages.error(request, "You cannot deactivate your own account.")
        else:
            user.is_active = not user.is_active
            user.save(update_fields=['is_active'])
            status = "activated" if user.is_active else "deactivated"
            messages.success(request, f"User '{user.username}' has been {status}.")
        return redirect('accounts:user_list')
