"""Back-office views. Every view declares its permissions (deny by default)."""

from datetime import timedelta
from typing import Any

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.views.generic import FormView, ListView, TemplateView

from apps.accounts import selectors as account_selectors
from apps.accounts import services as account_services
from apps.accounts.forms import RoleAssignmentForm
from apps.accounts.models import User
from apps.accounts.permissions import StaffRequiredMixin, authenticated_user
from apps.audit import selectors as audit_selectors


class DashboardView(StaffRequiredMixin, TemplateView):
    template_name = "panel/dashboard.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        user = authenticated_user(self.request)
        since = timezone.now() - timedelta(hours=24)
        context.update(
            role=account_services.role_of(user),
            stores=account_selectors.stores_for(user),
            staff_count=account_selectors.staff_members().count(),
            customer_count=User.objects.filter(is_staff=False, is_active=True).count(),
        )
        if user.has_perm("audit.view_auditlog"):
            context["recent_audit"] = audit_selectors.audit_entries()[:8]
        if user.has_perm("audit.view_securityevent"):
            context["security_24h"] = (
                audit_selectors.security_events().filter(created_at__gte=since).count()
            )
        return context


class StaffListView(StaffRequiredMixin, FormView):
    required_permissions = ("accounts.access_panel", "accounts.manage_staff")
    template_name = "panel/staff_list.html"
    form_class = RoleAssignmentForm

    def get_form_kwargs(self) -> dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs["actor"] = authenticated_user(self.request)
        return kwargs

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["staff"] = [
            (member, account_services.role_of(member))
            for member in account_selectors.staff_members()
        ]
        return context

    def form_valid(self, form: RoleAssignmentForm) -> HttpResponse:
        target = User.objects.filter(email=form.cleaned_data["email"].strip().lower()).first()
        if target is None:
            form.add_error("email", "No existe una cuenta con ese correo.")
            return self.form_invalid(form)
        try:
            account_services.assign_role(
                actor=authenticated_user(self.request),
                user=target,
                role=form.cleaned_data["role"],
                request=self.request,
            )
        except (PermissionDenied, ValidationError) as error:
            form.add_error(None, str(error) or "No tienes permiso para esta asignación.")
            return self.form_invalid(form)
        messages.success(
            self.request, f"Rol actualizado: {target.email} → {form.cleaned_data['role']}."
        )
        return redirect("panel:staff")


class AuditLogListView(StaffRequiredMixin, ListView):
    required_permissions = ("accounts.access_panel", "audit.view_auditlog")
    template_name = "panel/audit_list.html"
    paginate_by = 50
    context_object_name = "entries"

    def get_queryset(self) -> Any:
        return audit_selectors.audit_entries()


class SecurityEventListView(StaffRequiredMixin, ListView):
    required_permissions = ("accounts.access_panel", "audit.view_securityevent")
    template_name = "panel/security_list.html"
    paginate_by = 50
    context_object_name = "events"

    def get_queryset(self) -> Any:
        return audit_selectors.security_events()
