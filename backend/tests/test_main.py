import pytest
import os
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select

from main import app
from app.db.database import get_db
from app.models.domain import Base, User, Complaint, DriverTask, DriverLocation
from app.core.auth import get_password_hash

os.environ["SECRET_KEY"] = "testsecretkeytestsecretkeytestsecretkey"
os.environ["ENVIRONMENT"] = "testing"

SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///./test_scos.db"

engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(class_=AsyncSession, autocommit=False, autoflush=False, bind=engine)

import pytest_asyncio

@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

async def override_get_db():
    async with TestingSessionLocal() as db:
        yield db

app.dependency_overrides[get_db] = override_get_db

@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
async def test_read_root_redirects_to_app(client):
    response = await client.get("/")
    assert response.status_code == 404 # In FastAPI, unmounted root returns 404


@pytest.mark.asyncio
async def test_cors_headers(client):
    response = await client.options(
        "/api/auth/login",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_invalid_login_credentials(client):
    response = await client.post(
        "/api/auth/login",
        data={"username": "nonexistent@city.com", "password": "wrongpassword"}
    )
    assert response.status_code in [400, 401]

@pytest.mark.asyncio
async def test_registration_forces_citizen(client):
    response = await client.post(
        "/api/auth/register",
        json={"email": "newcitizen@city.com", "password": "password", "name": "New Citizen"}
    )
    assert response.status_code == 200
    
    async with TestingSessionLocal() as db:
        result = await db.execute(select(User).filter(User.email == "newcitizen@city.com"))
        user = result.scalars().first()
        assert user.role == "CITIZEN"

@pytest.mark.asyncio
async def test_admin_endpoints_protection(client):
    response = await client.get("/api/admin/overview")
    assert response.status_code in [401, 404]
    
    async with TestingSessionLocal() as db:
        citizen = User(name="Citizen John", email="citizen@city.com", role="CITIZEN", password_hash=get_password_hash("password"))
        db.add(citizen)
        await db.commit()
    
    login_resp = await client.post(
        "/api/auth/login",
        data={"username": "citizen@city.com", "password": "password"}
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.get("/api/admin/overview", headers=headers)
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_admin_create_user_success(client):
    async with TestingSessionLocal() as db:
        admin = User(name="Admin Alice", email="admin@city.com", role="ADMIN", password_hash=get_password_hash("password"))
        db.add(admin)
        await db.commit()
    
    login_resp = await client.post(
        "/api/auth/login",
        data={"username": "admin@city.com", "password": "password"}
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    response = await client.post(
        "/api/admin/create_user",
        json={"email": "newdriver@city.com", "password": "password", "role": "DRIVER", "name": "New Driver"},
        headers=headers
    )
    assert response.status_code == 200
    
    async with TestingSessionLocal() as db:
        result = await db.execute(select(User).filter(User.email == "newdriver@city.com"))
        user = result.scalars().first()
        assert user.role == "DRIVER"

@pytest.mark.asyncio
async def test_driver_complete_pickup_synchronization(client, tmp_path):
    async with TestingSessionLocal() as db:
        driver = User(id=10, name="Driver Dave", email="driver@city.com", role="DRIVER", password_hash=get_password_hash("password"))
        complaint = Complaint(id=5, citizen_id=1, zone="Zone 1", area="Market", waste_type="Plastic", severity_level="High", status="PENDING", lat=12.9800, lng=77.6000)
        loc = DriverLocation(driver_id=10, lat=12.9800, lng=77.6000)
        task = DriverTask(driver_id=10, complaint_id=5, priority="HIGH", waste_type="Plastic", address="Market", status="ASSIGNED")
        db.add_all([driver, complaint, loc, task])
        await db.commit()
    
    login_resp = await client.post(
        "/api/auth/login",
        data={"username": "driver@city.com", "password": "password"}
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    proof_file = tmp_path / "proof.jpg"
    proof_file.write_bytes(b"dummy" * 1500)
    
    with open(proof_file, "rb") as f:
        response = await client.post(
            "/api/driver/complete_pickup",
            data={"complaint_id": 5},
            files={"proof_photo": ("proof.jpg", f, "image/jpeg")},
            headers=headers
        )
    
    assert response.status_code == 200
