# OrderFlow — E-Commerce Order & Payment Management System

OrderFlow is a portfolio-ready commerce backend built with **Python, FastAPI and MySQL**. It demonstrates API design, relational data modeling, authentication, inventory reservation, transactional checkout, idempotent requests, payment-provider integration, webhooks, refunds, tests and container deployment.

> **Demo mode is safe to experiment with:** `PAYMENT_PROVIDER=mock` simulates payments and refunds locally. It never charges a real card or UPI account. Razorpay is an optional integration and requires your own test credentials.

## What it does

- Customer registration and login with Argon2 password hashing and JWT bearer tokens.
- Product catalogue, search and administrator-only product management.
- Customer shopping carts with stock validation.
- Transactional checkout that reserves inventory and snapshots product names, SKUs and prices into order lines.
- `Idempotency-Key` support on checkout to avoid duplicate orders when a client retries a request.
- Mock payment flow for local demos, plus optional Razorpay order creation and signed webhook verification.
- Full-order mock refunds and optional Razorpay refund requests.
- Role-based access control, order history, audit-style order events and sales/stock metrics.
- OpenAPI/Swagger docs, Docker, MySQL Compose, Alembic migrations and pytest tests.

## Architecture

```text
Browser storefront / API client
           |
           v
     FastAPI routers
           |
   Auth / validation / RBAC
           |
   Service-style transaction flows
           |
 SQLAlchemy 2.0 ORM + Alembic
           |
         MySQL

Payment provider: Mock (local) | Razorpay (test/live credentials)
Deployment: Docker image → Railway app service + Railway MySQL service
```

The backend is separated into `routes`, `schemas`, `models`, `core` and `db`. The storefront is intentionally lightweight HTML/CSS/JavaScript and is served by FastAPI from the same container.

## Run locally — easiest option (SQLite)

Python 3.11+ is recommended.

```bash
# 1. Open the project directory
cd orderflow

# 2. Create and activate a virtual environment
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

# 3. Install dependencies
python -m pip install -r requirements.txt

# 4. Create local configuration
# Windows PowerShell: Copy-Item .env.example .env
# macOS/Linux: cp .env.example .env

# 5. Start the API (development startup creates tables automatically)
uvicorn app.main:app --reload
```

Open:

- Storefront: http://127.0.0.1:8000
- Swagger API docs: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc
- Health check: http://127.0.0.1:8000/health

In a second terminal, with the same virtual environment activated:

```bash
python -m scripts.seed_demo
```

The demo catalogue contains six sample products. Register a customer from the storefront, add products, then checkout. In mock mode the UI automatically completes the simulated payment. No real payment credentials are needed.

## Run locally with MySQL and Docker

Docker Desktop must be running.

```bash
cp .env.example .env
Edit `.env` and replace `SECRET_KEY` with a unique random string of at least 32 characters.
docker compose up --build -d
```

The Compose file starts MySQL 8.4 and the API. The API container runs `alembic upgrade head` before Uvicorn starts. Open http://localhost:8000.

To seed the MySQL catalogue:

```bash
docker compose exec api python -m scripts.seed_demo
```

To create an administrator:

```bash
docker compose exec api python -m scripts.create_admin
```

Local Compose credentials are for development only. Change them before using this stack outside your machine.

## Create an administrator

New registrations are always assigned the `customer` role. This is intentional: users cannot make themselves administrators through the public API.

```bash
python -m scripts.create_admin
```

The script prompts for an email, name and password, creates an administrator, or promotes an existing account. Do not expose this script as a public HTTP endpoint.

## API reference

A committed OpenAPI snapshot is available at [`docs/openapi.json`](docs/openapi.json); the running `/docs` page is the live interactive reference.

All API endpoints are prefixed with `/api/v1`. Interactive details and request/response schemas are available at `/docs`.

| Method | Endpoint | Access | Purpose |
|---|---|---|---|
| POST | `/auth/register` | Public | Create a customer account |
| POST | `/auth/login` | Public | Get a JWT access token |
| GET | `/auth/me` | Customer/admin | Current account |
| GET | `/products` | Public | Search/list active products |
| GET | `/products/{id}` | Public | Product detail |
| POST | `/products` | Admin | Create product |
| PATCH | `/products/{id}` | Admin | Update product/stock |
| DELETE | `/products/{id}` | Admin | Archive product |
| GET | `/cart` | Customer | View current cart |
| POST | `/cart/items` | Customer | Add a product |
| PATCH | `/cart/items/{id}` | Customer | Change quantity |
| DELETE | `/cart/items/{id}` | Customer | Remove a cart item |
| POST | `/orders/checkout` | Customer | Reserve stock and create order |
| GET | `/orders/mine` | Customer | List own orders |
| GET | `/orders/{id}` | Owner/admin | Order detail |
| PATCH | `/orders/{id}/cancel` | Owner/admin | Cancel an unpaid order and restore stock |
| POST | `/orders/{id}/payments` | Owner/admin | Create a payment attempt |
| POST | `/payments/{id}/simulate` | Owner/admin, mock only | Simulate payment success/failure |
| POST | `/payments/webhook` | Razorpay signature | Process signed Razorpay webhooks |
| POST | `/payments/{id}/refunds` | Owner/admin | Request a full refund |
| GET | `/payments/mine` | Customer | List own payment attempts |
| GET | `/admin/metrics` | Admin | Dashboard metrics |
| GET | `/orders` | Admin | List all orders |
| GET | `/admin/payments` | Admin | List recent payments |

### Typical customer flow

1. `POST /auth/register` with `{ "name": "Demo Customer", "email": "customer@example.com", "password": "strong-password" }`.
2. Copy `access_token` from the response and click **Authorize** in Swagger. Enter `Bearer <token>`.
3. `GET /products`, then `POST /cart/items` with `{ "product_id": 1, "quantity": 1 }`.
4. `POST /orders/checkout` with a shipping address and an `Idempotency-Key` header such as `checkout-demo-001`.
5. `POST /orders/{order_id}/payments`.
6. In mock mode, `POST /payments/{payment_id}/simulate` with `{ "success": true }`.
7. `GET /orders/mine` to confirm the order status is `paid`.

### Checkout request example

```json
{
  "shipping_address": {
    "full_name": "Demo Customer",
    "line1": "101 Example Street",
    "city": "Mumbai",
    "state": "Maharashtra",
    "postal_code": "400001",
    "country": "India",
    "phone": "9999999999"
  }
}
```

## Payment configuration

### Mock payments (default)

```env
PAYMENT_PROVIDER=mock
```

A mock payment can be succeeded or failed using `/payments/{payment_id}/simulate`. Failure cancels the pending order and restores the reserved stock. Mock refunds transition a successful payment/order to `refunded` immediately. This is intended for local demos and automated tests only.

### Razorpay Test Mode (optional)

Set these variables in a private `.env` or your hosting provider's secret-variable panel:

```env
PAYMENT_PROVIDER=razorpay
RAZORPAY_KEY_ID=rzp_test_...
RAZORPAY_KEY_SECRET=...
RAZORPAY_WEBHOOK_SECRET=...
```

Configure the Razorpay webhook URL as `https://YOUR-DOMAIN/api/v1/payments/webhook` and subscribe to `payment.captured`, `payment.failed`, `refund.processed` and `refund.failed`. The backend verifies `X-Razorpay-Signature` using the raw request body before updating an order. The backend endpoint creates a Razorpay order; a production browser checkout UI and complete reconciliation/monitoring should be added before handling live payments. Do not put secret keys in frontend code or commit them to Git.

## Deploy to Railway

The repository includes a `Dockerfile` and `railway.json`. The intended Railway layout is one app service plus one MySQL service:

1. Create a Railway project and add a **MySQL** service.
2. Deploy this GitHub repository as a separate app service (Railway detects the Dockerfile).
3. Add the app variables below. Use Railway's variable-reference picker to reference the MySQL service's connection URL; set the value in `DATABASE_URL`.
4. Generate a long random `SECRET_KEY` in Railway's variable panel.
5. Set `ENVIRONMENT=production`, `PAYMENT_PROVIDER=mock`, and `CORS_ORIGINS` to the deployed app's origin (for example, `https://your-app.up.railway.app`).
6. Deploy. The configured start command applies Alembic migrations and starts Uvicorn on Railway's `$PORT`.
7. Confirm `https://YOUR-DOMAIN/health` returns `{"status":"ok","service":"orderflow-api"}` and `https://YOUR-DOMAIN/docs` loads.
8. Open the Railway service shell and run `python -m scripts.seed_demo`; run `python -m scripts.create_admin` to create your admin account.

Required app variables:

```env
ENVIRONMENT=production
SECRET_KEY=<long-random-secret>
DATABASE_URL=<Railway MySQL connection URL>
PAYMENT_PROVIDER=mock
CORS_ORIGINS=https://<your-public-app-domain>
```

Do not commit real `.env` values. The included `.env.example` contains placeholders only. Railway billing, account verification, and service availability are managed by Railway and may vary; confirm costs in its dashboard before leaving services running.

## Tests

```bash
python -m pytest
```

The test suite covers authentication, protected routes, storefront/static asset serving, idempotent checkout, successful mock payment and inventory restoration on failed payment. GitHub Actions runs the same suite on pushes and pull requests.

Tests use a temporary SQLite database and mock payment mode, so they do not need a running MySQL server or any gateway credentials.

## Data model

- `users`: customers and administrators.
- `products`: catalogue, SKU, price and available stock.
- `cart_items`: one cart row per user/product pair.
- `orders`: order state, totals, shipping snapshot and idempotency key.
- `order_items`: immutable purchase-time product/price snapshots.
- `payments`: provider order/payment IDs and payment state.
- `refunds`: refund requests and provider outcome state.
- `order_events`: event trail for checkout/payment/cancellation/refund changes.

## Engineering notes and known limitations

- Monetary values use `Decimal`/SQL `NUMERIC`, not binary floats.
- Checkout uses a database transaction, `SELECT ... FOR UPDATE` on products where supported, and conditional stock decrement updates. This protects inventory from overselling across concurrent checkouts on MySQL. SQLite is used for local convenience and tests; it does not provide the same row-locking semantics as MySQL.
- Idempotency keys are scoped to a user before storage. Reusing a key returns the original order instead of creating a second one.
- Payment webhooks are signature-checked and duplicate processed events are ignored.
- This is a portfolio/demo foundation, not a certified production commerce system. Before live use, add rate limiting, email verification/password reset, structured observability, tax/shipping rules, refund reconciliation, webhook retry/dead-letter handling, database backup strategy, stronger admin audit controls, and a complete hosted payment checkout flow.
