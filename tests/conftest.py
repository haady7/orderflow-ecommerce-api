import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.core.config import settings


@pytest.fixture()
def client():
    test_engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False, expire_on_commit=False)
    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.state.test_session_local = TestingSessionLocal
    old_environment = settings.environment
    old_secret = settings.secret_key
    settings.environment = "test"
    settings.secret_key = "test-secret-key-at-least-32-chars-long"
    with TestClient(app) as test_client:
        yield test_client
    settings.environment = old_environment
    settings.secret_key = old_secret
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()


@pytest.fixture()
def customer_token(client):
    response = client.post("/api/v1/auth/register", json={"name": "Test Customer", "email": "test@example.com", "password": "secure-pass-123"})
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


@pytest.fixture()
def customer_headers(customer_token):
    return {"Authorization": f"Bearer {customer_token}"}
