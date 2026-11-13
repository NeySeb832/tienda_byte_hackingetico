"""HTTP views for the cms app. Views orchestrate only: no business logic here."""

from typing import Any

from django.http import Http404
from django.views.generic import TemplateView

from apps.cms.selectors import current_legal_document


class LegalDocumentView(TemplateView):
    template_name = "cms/legal_document.html"
    kind = ""

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        document = current_legal_document(self.kind)
        if document is None:
            raise Http404
        context["document"] = document
        return context
