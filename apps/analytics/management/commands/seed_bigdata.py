"""Generate the synthetic sales history (bronze) and build the lake. Usage: seed_bigdata [--dias 730]."""

from decimal import Decimal
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.analytics import pipeline, synthetic
from apps.catalog.models import ProductVariant
from apps.inventory.models import Store


class Command(BaseCommand):
    help = "Genera el histórico sintético de ventas y construye el data lake (bronce, plata, oro)."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--dias", type=int, default=730)
        parser.add_argument("--pedidos-dia", type=int, default=45)

    def handle(self, *args: Any, **options: Any) -> None:
        variants = list(ProductVariant.objects.filter(is_active=True).select_related("product"))
        stores = list(
            Store.objects.filter(is_active=True, kind=Store.Kind.STORE).values_list(
                "code", flat=True
            )
        )
        if not variants or not stores:
            raise CommandError("Primero carga el catálogo con seed_demo.")
        catalog = [
            synthetic.CatalogItem(
                v.sku,
                v.price,
                float(max(v.product.popularity, 5)) / (1 + float(v.price / Decimal(1_000_000))),
            )
            for v in variants
        ]
        base = pipeline.lake()
        rows = synthetic.write_csv(
            base / "bronze" / "synthetic_sales.csv",
            synthetic.generate(
                catalog,
                stores,
                days=options["dias"],
                end=timezone.localdate(),
                orders_per_day=options["pedidos_dia"],
            ),
        )
        self.stdout.write(f"Bronce: {rows} líneas sintéticas.")
        stats = pipeline.run()
        self.stdout.write(self.style.SUCCESS(f"Lago listo: {stats}"))
