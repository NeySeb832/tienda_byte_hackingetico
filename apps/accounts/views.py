"""HTTP views for the accounts app ("Mi cuenta"). Views orchestrate only."""

import json
from typing import Any

from allauth.mfa.utils import is_mfa_enabled
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import FormView, TemplateView
from django_ratelimit.decorators import ratelimit

from apps.accounts import selectors, services
from apps.accounts.forms import AccountDeletionForm, AddressForm, ProfileForm
from apps.accounts.models import Address, CustomerProfile
from apps.accounts.permissions import authenticated_user
from apps.audit.services import record_event


class AccountDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/dashboard.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        user = authenticated_user(self.request)
        context.update(
            addresses=selectors.addresses_for(user)[:3],
            address_count=selectors.addresses_for(user).count(),
            mfa_enabled=is_mfa_enabled(user),
            consent=selectors.consents_for(user).first(),
        )
        return context


class ProfileView(LoginRequiredMixin, FormView):
    template_name = "accounts/profile_form.html"
    form_class = ProfileForm
    success_url = reverse_lazy("accounts:profile")

    def get_initial(self) -> dict[str, Any]:
        user = authenticated_user(self.request)
        profile = CustomerProfile.objects.filter(user=user).first()
        return {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "document_type": profile.document_type if profile else "",
            "document_number": profile.document_number if profile else "",
            "phone": profile.phone if profile else "",
            "marketing_opt_in": profile.marketing_opt_in if profile else False,
        }

    def form_valid(self, form: ProfileForm) -> HttpResponse:
        services.update_profile(
            authenticated_user(self.request), form.cleaned_data, request=self.request
        )
        messages.success(self.request, "Guardamos tus datos.")
        return super().form_valid(form)


class AddressListView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/address_list.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["addresses"] = selectors.addresses_for(authenticated_user(self.request))
        context["max_addresses"] = services.MAX_ADDRESSES
        return context


class AddressFormView(LoginRequiredMixin, FormView):
    template_name = "accounts/address_form.html"
    form_class = AddressForm
    success_url = reverse_lazy("accounts:addresses")

    def get_address(self) -> Address | None:
        public_id = self.kwargs.get("public_id")
        return (
            selectors.address_for(authenticated_user(self.request), public_id)
            if public_id
            else None
        )

    def get_form_kwargs(self) -> dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.get_address()
        return kwargs

    def form_valid(self, form: AddressForm) -> HttpResponse:
        try:
            services.save_address(
                authenticated_user(self.request), form.save(commit=False), request=self.request
            )
        except ValidationError as error:
            form.add_error(None, error)
            return self.form_invalid(form)
        messages.success(self.request, "Dirección guardada.")
        return super().form_valid(form)


class AddressDeleteView(LoginRequiredMixin, View):
    def get(self, request: HttpRequest, public_id: str) -> HttpResponse:
        address = selectors.address_for(authenticated_user(request), public_id)
        return render(request, "accounts/address_confirm_delete.html", {"address": address})

    def post(self, request: HttpRequest, public_id: str) -> HttpResponse:
        address = selectors.address_for(authenticated_user(request), public_id)
        services.delete_address(authenticated_user(request), address, request=request)
        messages.success(request, "Dirección eliminada.")
        return redirect("accounts:addresses")


class PrivacyView(LoginRequiredMixin, FormView):
    template_name = "accounts/privacy.html"
    form_class = AccountDeletionForm

    def get_form_kwargs(self) -> dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs["user"] = authenticated_user(self.request)
        return kwargs

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["consents"] = selectors.consents_for(authenticated_user(self.request))
        return context

    def form_valid(self, form: AccountDeletionForm) -> HttpResponse:
        user = authenticated_user(self.request)
        services.delete_account(user, request=self.request)
        logout(self.request)
        messages.success(self.request, "Eliminamos tu cuenta y tus datos personales.")
        return redirect("core:home")


@method_decorator(ratelimit(key="user", rate="5/h", method="GET", block=True), name="get")
class DataExportView(LoginRequiredMixin, View):
    def get(self, request: HttpRequest) -> HttpResponse:
        data = services.export_personal_data(authenticated_user(request))
        record_event(
            "accounts.data_exported",
            actor=authenticated_user(request),
            target=authenticated_user(request),
            request=request,
        )
        response = HttpResponse(
            json.dumps(data, ensure_ascii=False, indent=2), content_type="application/json"
        )
        response["Content-Disposition"] = 'attachment; filename="mis-datos-byte.json"'
        response["Cache-Control"] = "no-store"
        return response
