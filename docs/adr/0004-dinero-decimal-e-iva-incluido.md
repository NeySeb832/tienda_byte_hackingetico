# ADR-0004: Dinero en Decimal con IVA incluido

- **Estado:** Aceptada
- **Fecha:** 2026-11-12

## Contexto
La tienda opera en COP con un IVA del 19 % (las tarjetas de regalo, por ejemplo, van excluidas). El
Estatuto del Consumidor (Ley 1480 de 2011, art. 26) obliga a informar el precio final con impuestos
incluidos. La factura (simulada) necesita la base gravable y el IVA por separado. Wompi recibe los
montos en centavos.

## Decisión
- Todo valor monetario usa `DecimalField(max_digits=14, decimal_places=2)`.
- Los precios de catálogo **incluyen IVA**. El desglose se calcula por línea con
  `apps.core.money.split_vat(gross, rate)`: `base = round(gross / (1 + rate))` e `iva = gross - base`.
- El redondeo es `ROUND_HALF_UP` a centavos; los precios que se muestran son en pesos enteros.
- `to_money()` **rechaza `float`**, así que ningún cálculo pasa por punto flotante.
- El formato en pantalla es `$ 1.299.900` (punto para miles, coma para decimales), con `format_cop()` y
  el filtro de plantilla `cop`.

## Consecuencias
- El precio que ve el cliente es exactamente el que paga.
- La base más el IVA siempre suma el bruto, sin descuadres de centavos.
- La conversión a centavos para la pasarela ocurre en un único lugar (`payments`, Fase 4).

## Alternativas consideradas
- **Enteros en pesos**: es más simple, pero complica el desglose del IVA y los descuentos porcentuales.
- **Precios sin IVA**: obliga a calcular el precio final en cada vista y arriesga mostrar precios que
  incumplen la ley.
