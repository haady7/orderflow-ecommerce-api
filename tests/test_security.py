def test_protected_route_rejects_anonymous_request(client):
    response = client.get("/api/v1/cart")
    assert response.status_code == 401


def test_public_product_catalogue_is_accessible(client):
    response = client.get("/api/v1/products")
    assert response.status_code == 200
    assert response.json() == []


def test_customer_cannot_access_admin_metrics(client, customer_headers):
    response = client.get("/api/v1/admin/metrics", headers=customer_headers)
    assert response.status_code == 403


def test_storefront_and_api_docs_are_served(client):
    home = client.get("/")
    docs = client.get("/docs")
    static_js = client.get("/static/app.js")
    assert home.status_code == 200 and "Commerce" in home.text
    assert docs.status_code == 200
    assert static_js.status_code == 200 and "loadProducts" in static_js.text
