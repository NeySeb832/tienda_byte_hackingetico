from django.urls import path

from apps.cms.models import LegalDocument
from apps.cms.views import LegalDocumentView

app_name = "cms"

urlpatterns = [
    path(
        "legal/privacidad/",
        LegalDocumentView.as_view(kind=LegalDocument.Kind.PRIVACY),
        name="privacy",
    ),
    path(
        "legal/terminos/",
        LegalDocumentView.as_view(kind=LegalDocument.Kind.TERMS),
        name="terms",
    ),
]
