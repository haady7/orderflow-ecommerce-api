from decimal import Decimal
from sqlalchemy import select
from app.models import Product, User


def add_product(client, name="Test Headphones", sku="TEST-001", price="100.00", stock=5):
    # Product creation is administrator-only; for test setup insert through the overridden DB session.
    db = client.app.state.test_session_local()
    try:
        product = Product(name=name, sku=sku, price=Decimal(price), stock=stock, category="Electronics", description="Test item")
        db.add(product)
        db.commit()
        db.refresh(product)
        return product.id
    finally:
        db.close()


def test_customer_can_register_login_and_read_profile(client):
    created = client.post("/api/v1/auth/register", json={"name": "Test Customer", "email": "test@example.com", "password": "secure-pass-123"})
    assert created.status_code == 201
    login = client.post("/api/v1/auth/login", json={"email": "test@example.com", "password": "secure-pass-123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    profile = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert profile.status_code == 200
    assert profile.json()["role"] == "customer"


def test_checkout_is_idempotent_and_payment_updates_order(client, customer_headers):
    product_id = add_product(client)
    added = client.post("/api/v1/cart/items", headers=customer_headers, json={"product_id": product_id, "quantity": 2})
    assert added.status_code == 201
    assert added.json()["subtotal"] == "200.00"

    payload = {"shipping_address": {"full_name": "Test Customer", "line1": "101 Example Road", "city": "Mumbai", "state": "Maharashtra", "postal_code": "400001", "country": "India", "phone": "9999999999"}}
    headers = {**customer_headers, "Idempotency-Key": "test-checkout-once"}
    first = client.post("/api/v1/orders/checkout", headers=headers, json=payload)
    second = client.post("/api/v1/orders/checkout", headers=headers, json=payload)
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["status"] == "pending_payment"

    payment = client.post(f"/api/v1/orders/{first.json()['id']}/payments", headers=customer_headers)
    assert payment.status_code == 201, payment.text
    settled = client.post(f"/api/v1/payments/{payment.json()['id']}/simulate", headers=customer_headers, json={"success": True})
    assert settled.status_code == 200, settled.text
    assert settled.json()["status"] == "succeeded"
    order = client.get(f"/api/v1/orders/{first.json()['id']}", headers=customer_headers)
    assert order.json()["status"] == "paid"
    cart = client.get("/api/v1/cart", headers=customer_headers)
    assert cart.json()["items"] == []


def test_failed_payment_restores_reserved_stock(client, customer_headers):
    product_id = add_product(client, name="Limited Widget", sku="TEST-002", stock=1)
    client.post("/api/v1/cart/items", headers=customer_headers, json={"product_id": product_id, "quantity": 1})
    payload = {"shipping_address": {"full_name": "Test Customer", "line1": "101 Example Road", "city": "Mumbai", "state": "Maharashtra", "postal_code": "400001", "country": "India", "phone": "9999999999"}}
    order = client.post("/api/v1/orders/checkout", headers=customer_headers, json=payload)
    assert order.status_code == 201
    payment = client.post(f"/api/v1/orders/{order.json()['id']}/payments", headers=customer_headers)
    failed = client.post(f"/api/v1/payments/{payment.json()['id']}/simulate", headers=customer_headers, json={"success": False})
    assert failed.status_code == 200
    assert failed.json()["status"] == "failed"

    db = client.app.state.test_session_local()
    try:
        product = db.get(Product, product_id)
        assert product.stock == 1
    finally:
        db.close()
