"""BI dashboard (gold layer of the data lake). Read-only; analysts and managers."""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views import View

from apps.accounts.permissions import StaffRequiredMixin
from apps.analytics import bi


class BiDashboardView(StaffRequiredMixin, View):
    required_permissions = ("orders.view_sales_report",)

    def get(self, request: HttpRequest) -> HttpResponse:
        if not bi.gold_ready():
            return render(request, "panel/bi.html", {"ready": False})
        return render(request, "panel/bi.html", {"ready": True, "data": bi.dashboard()})
