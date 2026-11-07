# OrderFlow — E-Commerce Order & Payment Management System

A portfolio-ready e-commerce backend built with **Python, FastAPI and MySQL**.

## Source code

The complete project source is included in [orderflow-source-code.zip](./orderflow-source-code.zip). Download the archive and extract it; the application files are under the `orderflow/` directory.

## Highlights

- FastAPI REST API with JWT authentication and role-based authorization
- MySQL-compatible SQLAlchemy 2.0 models and Alembic migrations
- Product catalogue, shopping cart, transactional checkout and order history
- Inventory reservation/restoration and checkout idempotency
- Mock payments for safe demos and optional Razorpay test-mode integration
- Payment webhook signature verification and refund workflow
- Admin metrics, storefront, Swagger/OpenAPI documentation
- Docker Compose, Railway configuration and GitHub Actions tests

## Run locally

1. Extract `orderflow-source-code.zip`.
2. Open a terminal in the extracted `orderflow/` folder.
3. Create a virtual environment and install requirements:

```bash
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
```

4. Copy `.env.example` to `.env`, then set a unique `SECRET_KEY`.
5. Start the application:

```bash
uvicorn app.main:app --reload
```

6. Seed demo products in another terminal:

```bash
python -m scripts.seed_demo
```

Open the storefront at http://127.0.0.1:8000 and API docs at http://127.0.0.1:8000/docs.

## Tests

```bash
python -m pytest
```

The test suite uses SQLite and mock payments; it does not require payment credentials.

## Payment safety

Mock payments are enabled by default. They do not charge real money. Razorpay is optional and should be tested with Razorpay test credentials first. Never commit `.env` files or secret keys.

## Deployment

The archive includes a Dockerfile, Docker Compose and Railway configuration. For hosted deployment, provision a MySQL service, configure the environment variables described in the full README inside the archive, and deploy the extracted source.
