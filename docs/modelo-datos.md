# Modelo de datos — Byte

Este documento describe el modelo de datos principal de Byte, organizado por dominio. Los diagramas
están en Mermaid; GitHub y la mayoría de editores los renderizan.

> **Estado:** en la Fase 1 se implementaron el usuario propio (`accounts.User`), los modelos base
> abstractos (`core.PublicIdModel`, `core.TimeStampedModel`) y las extensiones de PostgreSQL
> (`pg_trgm`, `unaccent`). El resto de entidades se implementa en la fase indicada en la tabla final.
> Los diagramas muestran solo los campos clave; el detalle completo vive en cada `models.py`.

## Reglas transversales

| Regla | Detalle | ADR |
|-------|---------|-----|
| Identificadores | La PK interna es `bigint` y nunca sale a URLs ni a la API. Hacia afuera solo se usa `public_id` (UUID4) o `slug`. | [0011](adr/0011-identificadores-publicos-y-usuario-email.md) |
| Usuario | El email es el login. Se guarda en minúsculas y un `CHECK` en la BD lo garantiza. No hay `username`. | [0011](adr/0011-identificadores-publicos-y-usuario-email.md) |
| Dinero | `Decimal(14,2)` en COP. Los precios **incluyen IVA**; el desglose base/IVA se hace por línea con `split_vat()`. Nunca se usa `float`. | [0004](adr/0004-dinero-decimal-e-iva-incluido.md) |
| Registros append-only | El kardex (`StockMovement`), los ledgers de puntos y de crédito, y `AuditLog` solo reciben inserciones. Las correcciones se hacen con movimientos inversos. | [0001](adr/0001-monolito-modular-con-servicios.md) |
| Snapshots | `Order` y `OrderLine` copian precio, nombre, SKU y dirección, así un pedido no cambia aunque cambie el catálogo. | — |
| Stock | Hay `CHECK (on_hand >= 0)` y `CHECK (reserved <= on_hand)`. Toda modificación va en `select_for_update()` dentro de `transaction.atomic()`. | — |
| Separación de funciones | `CHECK (approved_by <> created_by)` en ajustes de inventario, descuentos altos, reembolsos y órdenes de compra. | [0003](adr/0003-permisos-de-objeto-propios.md) |
| Datos sensibles | El documento, el teléfono y los códigos digitales se cifran en reposo (MultiFernet). Para buscar por documento se usa un *blind index* HMAC. | — |
| Analítica sin PII | El usuario se seudonimiza como `HMAC-SHA256(user_id, pepper)` en los eventos y en la capa Gold. | — |
| Supresión (Habeas Data) | Al anonimizar a un usuario se reemplaza su PII, pero los pedidos históricos se conservan con un snapshot anonimizado. | — |

## 1. Identidad, roles y auditoría

```mermaid
erDiagram
    User ||--o| CustomerProfile : "perfil"
    User ||--o{ Address : "direcciones"
    User ||--o{ ConsentRecord : "acepta"
    LegalDocument ||--o{ ConsentRecord : "versión de política"
    User }o--o{ Group : "rol"
    User ||--o{ StaffStoreAssignment : "sedes asignadas"
    Store ||--o{ StaffStoreAssignment : "personal"
    LoyaltyTier ||--o{ CustomerProfile : "nivel (VIP)"
    Department ||--o{ City : "municipios"
    City ||--o{ Address : "ubica"
    City ||--o{ Store : "ubica"
    User ||--o{ AuditLog : "actor"
    User ||--o{ SecurityEvent : "afectado"

    User {
        bigint id PK "interno, nunca en URLs"
        uuid public_id UK
        string email UK "login, CHECK minúsculas"
        bool is_staff
    }
    CustomerProfile {
        bigint user_id FK
        string document_number "cifrado + blind index"
        string phone "cifrado"
        bigint loyalty_tier_id FK
        int points_balance "caché del ledger"
    }
    Address {
        uuid public_id UK
        bigint user_id FK
        bigint city_id FK
        string line1
        bool is_default
    }
    ConsentRecord {
        bigint user_id FK
        bigint legal_document_id FK
        datetime accepted_at
        inet ip
        datetime revoked_at
    }
    AuditLog {
        uuid public_id UK
        bigint actor_id FK
        string action
        string target
        json before "PII enmascarada"
        json after "PII enmascarada"
        inet ip
        string request_id "correlación"
        string row_hash "cadena anti-manipulación"
    }
    SecurityEvent {
        string kind "fuerza bruta, ráfaga 403, rol admin, export masivo"
        string severity
        inet ip
        datetime alerted_at
    }
```

## 2. Catálogo y precios

El precio que cobra el servidor se resuelve en este orden:

1. Precio de la variante: fijo, o base + modificadores de cada opción.
2. `PriceRule` vigente (incluye los precios VIP).
3. `FlashSale`.
4. Cupón, aplicado en el checkout.

```mermaid
erDiagram
    Brand ||--o{ Product : "marca"
    Category ||--o{ Product : "categoría"
    Category |o--o{ Category : "padre"
    Product }o--o{ Platform : "compatible con"
    Product ||--o| GameDetails : "ficha de juego"
    GameDetails }o--o{ Genre : "géneros"
    Attribute ||--o{ AttributeValue : "valores"
    Product ||--o{ ProductOption : "opciones configurables"
    Attribute ||--o{ ProductOption : "usa"
    ProductOption ||--o{ ProductOptionValue : "valores habilitados"
    AttributeValue ||--o{ ProductOptionValue : "valor"
    Product ||--|{ ProductVariant : "variantes"
    ProductVariant }o--o{ AttributeValue : "combinación"
    Product ||--o{ ProductImage : "galería"
    ProductVariant |o--o{ ProductImage : "imagen propia"
    Bundle ||--|{ BundleItem : "incluye"
    Product ||--o{ BundleItem : "producto"
    ProductVariant ||--o{ PriceHistory : "historial"
    ProductVariant ||--o{ ScheduledPriceChange : "precio futuro"
    LoyaltyTier |o--o{ PriceRule : "exclusivo VIP"

    Product {
        uuid public_id UK
        string slug UK
        string product_type "console/game/accessory/collectible/gift_card/service"
        string pricing_mode "base+modificadores o fijo por variante"
        decimal base_price "IVA incluido"
        string tax_class "iva_19 / excluido"
        bool is_preorder
        date release_date
        int max_per_order
        tsvector search_vector "GIN + pg_trgm"
    }
    ProductVariant {
        uuid public_id UK
        string sku UK
        string barcode
        decimal price_override "si es fijo por variante"
        string combination_key "único por producto"
        bool is_serialized "consolas: serial/IMEI"
        int warranty_months "según condición"
    }
    Attribute {
        string code UK "model/storage/edition/condition/region"
        string name
    }
    AttributeValue {
        string value "Slim, 1 TB, Usado grado A"
        json meta
    }
    ProductOptionValue {
        decimal price_modifier
    }
    GameDetails {
        string esrb
        string pegi
        json languages
        string multiplayer
        string developer
        string format "físico/digital"
    }
    PriceHistory {
        decimal price
        datetime valid_from
        datetime valid_to
    }
    ScheduledPriceChange {
        decimal new_price
        datetime starts_at
        bigint created_by FK
        bigint approved_by FK
    }
    PriceRule {
        string scope "categoría/marca/plataforma/producto"
        string adjustment "porcentaje/fijo"
        decimal value
        datetime starts_at
        datetime ends_at
        int priority
    }
```

## 3. Inventario y compras

```mermaid
erDiagram
    Store ||--o{ StockItem : "stock por sede"
    ProductVariant ||--o{ StockItem : "variante"
    StockItem ||--o{ StockMovement : "kardex"
    StockItem ||--o{ StockReservation : "reservas"
    ProductVariant ||--o{ SerialUnit : "unidades serializadas"
    Store ||--o{ SerialUnit : "ubicación"
    ProductVariant ||--o{ DigitalKey : "códigos digitales"
    Store ||--o{ InventoryAdjustment : "ajustes y conteos"
    InventoryAdjustment ||--|{ AdjustmentLine : "líneas"
    Store ||--o{ StockTransfer : "origen / destino"
    StockTransfer ||--|{ TransferLine : "líneas"
    Supplier ||--o{ PurchaseOrder : "provee"
    Store ||--o{ PurchaseOrder : "destino"
    PurchaseOrder ||--|{ PurchaseOrderLine : "líneas"
    PurchaseOrder ||--o{ GoodsReceipt : "recepciones parciales"
    GoodsReceipt ||--|{ GoodsReceiptLine : "líneas"
    PurchaseOrderLine ||--o{ GoodsReceiptLine : "recibe"

    Store {
        uuid public_id UK
        string code UK
        string kind "tienda/bodega"
        bool is_pickup_point
    }
    StockItem {
        int on_hand "CHECK >= 0"
        int reserved "CHECK <= on_hand"
        int in_transit
        decimal average_cost "promedio ponderado"
        int min_stock
        int reorder_point
    }
    StockMovement {
        uuid public_id UK
        string kind "compra/venta/ajuste/traslado/devolución/retoma"
        int quantity "con signo"
        decimal unit_cost
        int balance_after
        string reason
        bigint user_id FK
        string reference "documento origen"
    }
    StockReservation {
        int quantity
        bigint cart_id FK
        bigint order_id FK
        datetime expires_at "TTL"
        string status
    }
    SerialUnit {
        string serial UK "serial o IMEI"
        string status "en_stock/reservado/vendido/en_reparación"
    }
    DigitalKey {
        string code "cifrado"
        string status
        bigint order_line_id FK
    }
    InventoryAdjustment {
        uuid public_id UK
        string status "borrador/pendiente/aprobado/rechazado"
        bigint created_by FK
        bigint approved_by FK "CHECK distinto de created_by"
    }
    PurchaseOrder {
        uuid public_id UK
        string number UK
        string status "borrador/aprobada/parcial/recibida/cancelada"
        decimal total
    }
```

## 4. Venta: carrito, pedido, pago, envío y promociones

```mermaid
erDiagram
    User ||--o{ Cart : "carrito"
    Cart ||--o{ CartItem : "ítems"
    ProductVariant ||--o{ CartItem : "variante"
    User ||--o{ WishlistItem : "deseos y alertas"
    User |o--o{ Order : "pedidos"
    Order ||--|{ OrderLine : "líneas"
    ProductVariant ||--o{ OrderLine : "variante"
    Order ||--|{ OrderStatusEvent : "línea de tiempo"
    Order ||--o{ Payment : "pagos"
    Payment ||--o{ Refund : "reembolsos"
    Payment |o--o{ WebhookEvent : "eventos"
    InvoiceResolution ||--o{ Invoice : "numeración"
    Order ||--o| Invoice : "factura"
    Order ||--o{ Shipment : "envíos"
    Shipment ||--o{ ShipmentEvent : "seguimiento"
    ShippingZone ||--|{ ShippingRate : "tarifas"
    ShippingZone }o--o{ Department : "cubre"
    Coupon ||--o{ CouponRedemption : "usos"
    Order ||--o| CouponRedemption : "aplica"
    FlashSale ||--|{ FlashSaleItem : "ítems"
    User ||--o{ LoyaltyLedger : "puntos"
    User ||--o{ StoreCreditLedger : "crédito en tienda"
    Order ||--o{ ReturnRequest : "devoluciones RMA"
    ReturnRequest ||--|{ ReturnLine : "líneas"
    OrderLine ||--o{ ReturnLine : "devuelve"

    Cart {
        uuid public_id UK
        bigint user_id FK "nulo si invitado"
        string session_key
        string status "abierto/fusionado/convertido"
        datetime expires_at
    }
    Order {
        uuid public_id UK
        string number UK "BYT-2026-000123"
        string channel "web/pos"
        string status "máquina de estados"
        string fulfillment "envío/recoger"
        json address_snapshot
        decimal subtotal
        decimal discount_total
        decimal tax_total
        decimal shipping_total
        decimal total
    }
    OrderLine {
        string sku_snapshot
        string name_snapshot
        int quantity
        decimal unit_price "IVA incluido"
        decimal tax_rate
        decimal line_total
    }
    Payment {
        uuid public_id UK
        string reference UK "enviada a la pasarela"
        string gateway "wompi/fake/efectivo/datáfono/crédito"
        string gateway_txn_id
        decimal amount
        string status
    }
    WebhookEvent {
        string event_id UK "idempotencia"
        bool signature_valid
        string status
        json payload
    }
    Invoice {
        string number UK
        string cufe "simulado"
        bool is_test "documento de prueba"
    }
    Coupon {
        string code UK
        string kind "porcentaje/fijo/envío_gratis"
        decimal value
        decimal max_discount
        int per_user_limit
        bool first_order_only
    }
    LoyaltyLedger {
        int delta
        string reason "acumula/redime/vence/reverso"
        int balance_after
    }
```

Estados del pedido (máquina de estados en `orders/services.py`):

```mermaid
stateDiagram-v2
    [*] --> pendiente_de_pago
    pendiente_de_pago --> pagado : webhook aprobado
    pendiente_de_pago --> cancelado : pago rechazado / expiró la reserva
    pagado --> en_preparacion
    en_preparacion --> enviado
    en_preparacion --> listo_para_recoger
    enviado --> entregado
    listo_para_recoger --> entregado
    pagado --> cancelado : reembolso aprobado
    entregado --> devuelto : RMA aprobada
    entregado --> [*]
    cancelado --> [*]
    devuelto --> [*]
```

## 5. Postventa y operación

```mermaid
erDiagram
    User ||--o{ TradeInRequest : "solicita"
    TradeInRequest ||--|{ TradeInItem : "equipos"
    Product ||--o{ TradeInItem : "modelo"
    Product ||--o{ TradeInPriceGuide : "tabla de oferta"
    Store ||--o{ TradeInRequest : "sede de revisión"
    TradeInRequest |o--o| StoreCreditLedger : "abono"
    User ||--o{ ServiceTicket : "abre"
    ServiceTicket ||--o{ TicketUpdate : "bitácora"
    ServiceTicket ||--o{ TicketAttachment : "fotos validadas"
    OrderLine ||--o{ Warranty : "garantía"
    Warranty |o--o{ ServiceTicket : "cubre"
    SerialUnit |o--o{ ServiceTicket : "equipo"
    Product ||--o{ Review : "reseñas"
    OrderLine ||--o| Review : "compra verificada"
    Product ||--o{ Question : "preguntas"
    Question ||--o{ Answer : "respuestas"
    Store ||--o{ Register : "cajas"
    Register ||--o{ CashSession : "turnos"
    CashSession ||--o{ Order : "ventas POS"
    CashSession ||--o{ CashMovement : "ingresos y retiros"
    User ||--o{ Notification : "in-app"

    TradeInRequest {
        uuid public_id UK
        string status "cotizada/agendada/en_revisión/ofertada/aceptada/pagada"
        decimal estimated_offer
        decimal final_offer
        string payout "crédito/transferencia"
        bigint technician_id FK
    }
    ServiceTicket {
        uuid public_id UK
        string kind "reparación/garantía"
        string status
        bigint assigned_to FK
        decimal estimated_cost
    }
    TicketAttachment {
        string file "bucket privado, nombre aleatorio"
        string sha256
        int size
    }
    Review {
        int rating "CHECK 1..5"
        string body "sanitizado con nh3"
        string status "pendiente/aprobada/rechazada"
    }
    CashSession {
        decimal opening_amount
        decimal expected_cash
        decimal counted_cash
        decimal difference
        string status
    }
```

Otros modelos sin diagrama:
- `cms`: `Banner`, `Page`, `NewsPost` y `LegalDocument`.
- `core`: `SiteConfiguration` (singleton con los datos de la empresa y la resolución DIAN simulada) e `IdempotencyKey`.
- `notifications`: `NotificationPreference` y `EmailTemplate`.

## 6. Analítica: capa Gold (Parquet + DuckDB)

La capa Gold no son tablas de Django sino archivos Parquet que se consultan con DuckDB (Fase 7).

En PostgreSQL viven los modelos operativos de la analítica:
- `Event`: usuario seudonimizado, índice BRIN en `occurred_at`.
- `PipelineRun` y `DataQualityCheck`.
- `ModelRun`: guarda las métricas MAPE, silhouette y precisión/recall.
- `ProductAssociation`: alimenta la sección "comprados juntos".
- `DemandForecast` y `ReorderSuggestion`.
- `CustomerScore`: RFM, churn y CLV, que se llevan al CRM.
- `Insight` y `SavedReport`.

```mermaid
erDiagram
    dim_date ||--o{ fact_sales : "fecha"
    dim_product ||--o{ fact_sales : "producto"
    dim_customer ||--o{ fact_sales : "cliente"
    dim_store ||--o{ fact_sales : "sede"
    dim_channel ||--o{ fact_sales : "canal"
    dim_date ||--o{ fact_inventory_snapshot : "fecha"
    dim_product ||--o{ fact_inventory_snapshot : "producto"
    dim_store ||--o{ fact_inventory_snapshot : "sede"
    dim_date ||--o{ fact_events : "fecha"
    dim_product ||--o{ fact_events : "producto"
    dim_customer ||--o{ fact_events : "cliente"
    dim_channel ||--o{ fact_events : "canal"

    fact_sales {
        int date_key FK
        int product_key FK
        string customer_key FK "seudónimo HMAC, sin PII"
        int store_key FK
        int channel_key FK
        int quantity
        decimal net_amount
        decimal tax_amount
        decimal discount_amount
        decimal cost_amount
        decimal margin
        bool is_returned
    }
    fact_inventory_snapshot {
        int on_hand
        int reserved
        decimal stock_value
    }
    fact_events {
        string event_type "vista/búsqueda/carrito/checkout/compra"
        string session_hash
    }
    dim_customer {
        string customer_key PK
        string department
        string city
        string rfm_segment
        date first_order_date
    }
    dim_product {
        int product_key PK
        string category
        string platform
        string brand
        string condition
    }
```

## 7. Implementación por fase

| Fase | Entidades |
|------|-----------|
| 1 ✅ | `User`, `PublicIdModel`, `TimeStampedModel`, extensiones `pg_trgm` y `unaccent` |
| 2 | `CustomerProfile`, `Address`, `Department`, `City`, `ConsentRecord`, `LegalDocument`, `StaffStoreAssignment`, `Store` (base), `AuditLog`, `SecurityEvent` |
| 3 | `Platform`, `Brand`, `Category`, `Product`, `GameDetails`, `Genre`, `Attribute*`, `ProductOption*`, `ProductVariant`, `ProductImage`, `Bundle*`, `PriceRule`, `PriceHistory`, `ScheduledPriceChange` |
| 4 | `Cart*`, `WishlistItem`, `Order*`, `Payment`, `WebhookEvent`, `Refund`, `Invoice*`, `Shipping*`, `Shipment*`, `Coupon*`, `IdempotencyKey` y el núcleo del inventario (`StockItem`, `StockMovement`, `StockReservation`), porque el checkout reserva stock y debe probar que no hay sobreventa |
| 5 | `SerialUnit`, `DigitalKey`, `InventoryAdjustment*`, `StockTransfer*`, `Supplier`, `PurchaseOrder*`, `GoodsReceipt*`, `Register`, `CashSession`, `CashMovement`, `cms.*` |
| 6 | `TradeIn*`, `ServiceTicket*`, `Warranty`, `LoyaltyTier`, `LoyaltyLedger`, `StoreCreditLedger`, `FlashSale*`, `ReturnRequest*`, `Review`, `Question`, `Answer`, `Notification*` |
| 7 | `Event`, `PipelineRun`, `DataQualityCheck`, `ModelRun`, `ProductAssociation`, `DemandForecast`, `ReorderSuggestion`, `CustomerScore`, `Insight`, `SavedReport` y la capa Gold |
