# OrderFlow architecture notes

## Order lifecycle

```mermaid
stateDiagram-v2
    [*] --> pending_payment: Checkout reserves stock
    pending_payment --> paid: Verified payment captured
    pending_payment --> cancelled: Payment failed / user cancels
    pending_payment --> cancelled: Stock restored
    paid --> refunded: Full refund processed
    cancelled --> [*]
    refunded --> [*]
```

## Checkout sequence

```mermaid
sequenceDiagram
    actor Customer
    participant API as FastAPI
    participant DB as MySQL
    Customer->>API: POST /orders/checkout + Idempotency-Key
    API->>DB: Find previous order for key
    alt Retry of completed checkout request
        DB-->>API: Existing order
        API-->>Customer: Existing order response
    else New checkout
        API->>DB: BEGIN transaction
        API->>DB: Lock product rows (FOR UPDATE)
        API->>DB: Conditional stock decrement
        API->>DB: Insert order + order item snapshots + event
        API->>DB: Clear cart
        API->>DB: COMMIT
        API-->>Customer: Pending-payment order
    end
    Customer->>API: POST /orders/{id}/payments
    API-->>Customer: Payment attempt / provider order ID
    Customer->>API: Gateway checkout or mock simulation
    API->>DB: Verify state transition and persist result
    API-->>Customer: Updated payment state
```

## Relational model

```mermaid
erDiagram
    USERS ||--o{ CART_ITEMS : owns
    PRODUCTS ||--o{ CART_ITEMS : appears_in
    USERS ||--o{ ORDERS : places
    ORDERS ||--|{ ORDER_ITEMS : contains
    PRODUCTS o|--o{ ORDER_ITEMS : snapshot_source
    ORDERS ||--o{ PAYMENTS : has
    PAYMENTS ||--o{ REFUNDS : may_have
    ORDERS ||--o{ ORDER_EVENTS : records
    USERS {
        int id PK
        string email UK
        string password_hash
        string role
    }
    PRODUCTS {
        int id PK
        string sku UK
        decimal price
        int stock
    }
    ORDERS {
        int id PK
        int user_id FK
        string status
        decimal total
        string idempotency_key UK
    }
    PAYMENTS {
        int id PK
        int order_id FK
        string provider_order_id UK
        string status
    }
```

## Important implementation decisions

- Prices and totals are `Decimal` values stored in SQL `NUMERIC` columns to avoid floating-point currency errors.
- The order line stores product name, SKU and unit price at purchase time. A later catalogue edit therefore does not rewrite purchase history.
- `Idempotency-Key` values are namespaced with the authenticated user ID before being stored, avoiding cross-customer key collisions.
- MySQL checkout uses row locks plus a conditional stock decrement. A conditional update (`stock >= requested_quantity`) is still used as a final guard.
- Payment state changes are applied only after a valid mock action or a signature-verified Razorpay webhook.
- New registrations cannot self-assign the administrator role. Admin promotion is an explicit one-time CLI operation.
