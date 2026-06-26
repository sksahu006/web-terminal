import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.database import get_db
from app.main import app
from app.models.user import User


pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def unauth_client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as test_client:
        yield test_client

    app.dependency_overrides.clear()


async def test_register_creates_user_and_returns_tokens(unauth_client, db_session):
    response = await unauth_client.post(
        "/auth/register",
        json={"email": "Learner@Example.com", "password": "secret123", "username": "learner"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["user"]["email"] == "learner@example.com"
    assert body["user"]["username"] == "learner"

    result = await db_session.execute(select(User).where(User.email == "learner@example.com"))
    user = result.scalar_one()
    assert user.password_hash != "secret123"


async def test_login_returns_tokens_for_valid_credentials(unauth_client):
    await unauth_client.post(
        "/auth/register",
        json={"email": "learner@example.com", "password": "secret123", "username": "learner"},
    )

    response = await unauth_client.post(
        "/auth/login",
        json={"email": "learner@example.com", "password": "secret123"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["user"]["email"] == "learner@example.com"


async def test_login_rejects_wrong_password(unauth_client):
    await unauth_client.post(
        "/auth/register",
        json={"email": "learner@example.com", "password": "secret123", "username": "learner"},
    )

    response = await unauth_client.post(
        "/auth/login",
        json={"email": "learner@example.com", "password": "wrongpass"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


async def test_refresh_returns_new_access_token(unauth_client):
    register_response = await unauth_client.post(
        "/auth/register",
        json={"email": "learner@example.com", "password": "secret123", "username": "learner"},
    )
    refresh_token = register_response.json()["refresh_token"]

    response = await unauth_client.post("/auth/refresh", json={"refresh_token": refresh_token})

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"] == refresh_token


async def test_me_uses_email_password_access_token(unauth_client):
    register_response = await unauth_client.post(
        "/auth/register",
        json={"email": "learner@example.com", "password": "secret123", "username": "learner"},
    )
    access_token = register_response.json()["access_token"]

    response = await unauth_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == "learner@example.com"
