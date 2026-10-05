"""
SCOS Phase 2 Test Suite
Tests: role guards, business logic, security, reward redemption,
       pickup verification ownership, GPS validation, duplicate prevention.
"""
import pytest
import os
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select

from main import app
from app.db.database import get_db
from app.models.domain import Base, User, Complaint, DriverTask, DriverLocation, Reward, RewardRedemption
from app.core.auth import get_password_hash

os.environ["SECRET_KEY"] = "testsecretkeytestsecretkeytestsecretkey"
os.environ["ENVIRONMENT"] = "testing"

# Use the same DB file as test_main.py to avoid dependency_overrides collision
SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///./test_scos.db"

engine = create_async_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
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



# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

async def _create_user(db, *, email, role, name="Test", eco_points=0, id=None):
    kwargs = dict(name=name, email=email, role=role,
                  password_hash=get_password_hash("password"), eco_points=eco_points)
    if id is not None:
        kwargs["id"] = id
    user = User(**kwargs)
    db.add(user)
    await db.commit()
    return user


async def _login(client, email, password="password"):
    resp = await client.post("/api/auth/login", data={"username": email, "password": password})
    assert resp.status_code == 200, f"Login failed for {email}: {resp.text}"
    return resp.json()["access_token"]


async def _auth(client, email, password="password"):
    token = await _login(client, email, password)
    return {"Authorization": f"Bearer {token}"}


# ─────────────────────────────────────────────
# R1: Driver endpoint role guards
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_driver_endpoints_reject_unauthenticated(client):
    """Unauthenticated requests must get 401."""
    for path in ["/api/driver/dashboard", "/api/driver/assigned_tasks", "/api/driver/active_complaints"]:
        resp = await client.get(path)
        assert resp.status_code == 401, f"{path} should be 401 without auth, got {resp.status_code}"


@pytest.mark.asyncio
async def test_driver_endpoints_reject_citizen(client):
    """A CITIZEN token must get 403 on driver endpoints."""
    async with TestingSessionLocal() as db:
        await _create_user(db, email="citizen@t.com", role="CITIZEN")
    headers = await _auth(client, "citizen@t.com")
    for path in ["/api/driver/dashboard", "/api/driver/assigned_tasks", "/api/driver/active_complaints"]:
        resp = await client.get(path, headers=headers)
        assert resp.status_code == 403, f"{path} should be 403 for CITIZEN, got {resp.status_code}"


@pytest.mark.asyncio
async def test_driver_endpoints_reject_admin(client):
    """An ADMIN token must get 403 on driver endpoints."""
    async with TestingSessionLocal() as db:
        await _create_user(db, email="admin@t.com", role="ADMIN")
    headers = await _auth(client, "admin@t.com")
    for path in ["/api/driver/dashboard", "/api/driver/assigned_tasks", "/api/driver/active_complaints"]:
        resp = await client.get(path, headers=headers)
        assert resp.status_code == 403, f"{path} should be 403 for ADMIN, got {resp.status_code}"


@pytest.mark.asyncio
async def test_driver_endpoints_allow_driver(client):
    """A valid DRIVER token must get 200 on driver GET endpoints."""
    async with TestingSessionLocal() as db:
        await _create_user(db, email="driver@t.com", role="DRIVER")
    headers = await _auth(client, "driver@t.com")
    for path in ["/api/driver/dashboard", "/api/driver/assigned_tasks", "/api/driver/active_complaints"]:
        resp = await client.get(path, headers=headers)
        assert resp.status_code == 200, f"{path} should be 200 for DRIVER, got {resp.status_code}: {resp.text}"


# ─────────────────────────────────────────────
# R2: Citizen endpoint role guards
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_citizen_endpoints_reject_unauthenticated(client):
    for path in ["/api/citizen/dashboard", "/api/citizen/my_reports", "/api/citizen/rewards"]:
        resp = await client.get(path)
        assert resp.status_code == 401, f"{path} should be 401 without auth"


@pytest.mark.asyncio
async def test_citizen_endpoints_reject_driver(client):
    async with TestingSessionLocal() as db:
        await _create_user(db, email="driver@t.com", role="DRIVER")
    headers = await _auth(client, "driver@t.com")
    for path in ["/api/citizen/dashboard", "/api/citizen/my_reports", "/api/citizen/rewards"]:
        resp = await client.get(path, headers=headers)
        assert resp.status_code == 403, f"{path} should be 403 for DRIVER, got {resp.status_code}"


@pytest.mark.asyncio
async def test_citizen_endpoints_reject_admin(client):
    async with TestingSessionLocal() as db:
        await _create_user(db, email="admin@t.com", role="ADMIN")
    headers = await _auth(client, "admin@t.com")
    for path in ["/api/citizen/dashboard", "/api/citizen/my_reports", "/api/citizen/rewards"]:
        resp = await client.get(path, headers=headers)
        assert resp.status_code == 403, f"{path} should be 403 for ADMIN, got {resp.status_code}"


@pytest.mark.asyncio
async def test_citizen_endpoints_allow_citizen(client):
    async with TestingSessionLocal() as db:
        await _create_user(db, email="citizen@t.com", role="CITIZEN")
    headers = await _auth(client, "citizen@t.com")
    for path in ["/api/citizen/dashboard", "/api/citizen/my_reports", "/api/citizen/rewards"]:
        resp = await client.get(path, headers=headers)
        assert resp.status_code == 200, f"{path} should be 200 for CITIZEN, got {resp.status_code}: {resp.text}"


# ─────────────────────────────────────────────
# Login response includes eco_points
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_login_returns_eco_points(client):
    async with TestingSessionLocal() as db:
        await _create_user(db, email="citizen@t.com", role="CITIZEN", eco_points=1240)
    resp = await client.post("/api/auth/login", data={"username": "citizen@t.com", "password": "password"})
    assert resp.status_code == 200
    data = resp.json()
    assert "eco_points" in data, "Login response must include eco_points"
    assert data["eco_points"] == 1240, f"Expected 1240, got {data['eco_points']}"


# ─────────────────────────────────────────────
# Citizen report creates complaint + awards points
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_citizen_report_creates_complaint_and_awards_points(client):
    async with TestingSessionLocal() as db:
        await _create_user(db, email="citizen@t.com", role="CITIZEN", eco_points=0, id=1)

    headers = await _auth(client, "citizen@t.com")
    resp = await client.post(
        "/api/citizen/report_issue",
        json={"zone": "Zone A", "area": "Market", "lat": 12.97, "lng": 77.59,
              "waste_type": "Plastic", "severity_level": "HIGH"},
        headers=headers
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "id" in data
    assert data["points"] == 10, f"Expected 10 EcoPoints, got {data['points']}"

    # Verify complaint in DB
    async with TestingSessionLocal() as db:
        result = await db.execute(select(Complaint))
        complaints = result.scalars().all()
        assert len(complaints) == 1
        assert complaints[0].waste_type == "Plastic"
        assert complaints[0].status == "PENDING"

        result2 = await db.execute(select(User).filter(User.email == "citizen@t.com"))
        user = result2.scalars().first()
        assert user.eco_points == 10


# ─────────────────────────────────────────────
# Pickup: task/complaint ownership and state
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_complete_pickup_updates_complaint_to_resolved(client):
    """After complete_pickup, the complaint status must be RESOLVED."""
    async with TestingSessionLocal() as db:
        driver = User(id=20, name="D", email="driver@t.com", role="DRIVER",
                      password_hash=get_password_hash("password"))
        complaint = Complaint(id=10, citizen_id=1, zone="Z", area="A",
                              waste_type="Plastic", status="PENDING", lat=1.0, lng=1.0)
        task = DriverTask(driver_id=20, complaint_id=10, priority="HIGH",
                          waste_type="Plastic", address="A", status="ASSIGNED")
        db.add_all([driver, complaint, task])
        await db.commit()

    headers = await _auth(client, "driver@t.com")
    resp = await client.post("/api/driver/complete_pickup", data={"complaint_id": 10}, headers=headers)
    assert resp.status_code == 200, resp.text

    async with TestingSessionLocal() as db:
        result = await db.execute(select(Complaint).filter(Complaint.id == 10))
        complaint = result.scalars().first()
        assert complaint.status == "RESOLVED", f"Complaint should be RESOLVED, got {complaint.status}"

        result2 = await db.execute(select(DriverTask).filter(DriverTask.driver_id == 20))
        task = result2.scalars().first()
        assert task.status == "COMPLETED", f"Task should be COMPLETED, got {task.status}"
        assert task.completed_at is not None


@pytest.mark.asyncio
async def test_complete_pickup_rejects_wrong_driver(client):
    """Driver B cannot complete Driver A's task."""
    async with TestingSessionLocal() as db:
        driver_a = User(id=21, name="A", email="driver_a@t.com", role="DRIVER",
                        password_hash=get_password_hash("password"))
        driver_b = User(id=22, name="B", email="driver_b@t.com", role="DRIVER",
                        password_hash=get_password_hash("password"))
        complaint = Complaint(id=11, citizen_id=1, zone="Z", area="A", status="PENDING", lat=1.0, lng=1.0)
        task = DriverTask(driver_id=21, complaint_id=11, status="ASSIGNED",
                          waste_type="Plastic", address="A")
        db.add_all([driver_a, driver_b, complaint, task])
        await db.commit()

    # Driver B tries to complete Driver A's task
    headers = await _auth(client, "driver_b@t.com")
    resp = await client.post("/api/driver/complete_pickup", data={"complaint_id": 11}, headers=headers)
    assert resp.status_code == 404, f"Wrong driver should get 404, got {resp.status_code}"


@pytest.mark.asyncio
async def test_complete_pickup_rejects_duplicate(client):
    """Completing an already-completed pickup must be rejected with 409."""
    async with TestingSessionLocal() as db:
        driver = User(id=23, name="D", email="driver@t.com", role="DRIVER",
                      password_hash=get_password_hash("password"))
        complaint = Complaint(id=12, citizen_id=1, zone="Z", area="A", status="RESOLVED", lat=1.0, lng=1.0)
        task = DriverTask(driver_id=23, complaint_id=12, status="COMPLETED",
                          waste_type="Plastic", address="A")
        db.add_all([driver, complaint, task])
        await db.commit()

    headers = await _auth(client, "driver@t.com")
    resp = await client.post("/api/driver/complete_pickup", data={"complaint_id": 12}, headers=headers)
    assert resp.status_code == 409, f"Duplicate completion should get 409, got {resp.status_code}"


@pytest.mark.asyncio
async def test_complete_pickup_rejects_nonexistent_task(client):
    """Completing a task that doesn't exist must be rejected with 404."""
    async with TestingSessionLocal() as db:
        driver = User(id=24, name="D", email="driver@t.com", role="DRIVER",
                      password_hash=get_password_hash("password"))
        db.add(driver)
        await db.commit()

    headers = await _auth(client, "driver@t.com")
    resp = await client.post("/api/driver/complete_pickup", data={"complaint_id": 9999}, headers=headers)
    assert resp.status_code == 404


# ─────────────────────────────────────────────
# GPS coordinate validation
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_location_rejects_invalid_coordinates(client):
    """update_location must reject out-of-range GPS coordinates."""
    async with TestingSessionLocal() as db:
        await _create_user(db, email="driver@t.com", role="DRIVER")

    headers = await _auth(client, "driver@t.com")

    # lat > 90
    resp = await client.post("/api/driver/update_location",
                             data={"lat": 91.0, "lng": 77.0}, headers=headers)
    assert resp.status_code == 422, f"lat=91 should be rejected, got {resp.status_code}"

    # lng > 180
    resp = await client.post("/api/driver/update_location",
                             data={"lat": 12.0, "lng": 200.0}, headers=headers)
    assert resp.status_code == 422, f"lng=200 should be rejected, got {resp.status_code}"


@pytest.mark.asyncio
async def test_update_location_accepts_valid_coordinates(client):
    async with TestingSessionLocal() as db:
        await _create_user(db, email="driver@t.com", role="DRIVER")

    headers = await _auth(client, "driver@t.com")
    resp = await client.post("/api/driver/update_location",
                             data={"lat": 12.97, "lng": 77.59}, headers=headers)
    assert resp.status_code == 200


# ─────────────────────────────────────────────
# Reward redemption
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_redeem_reward_deducts_points_correctly(client):
    async with TestingSessionLocal() as db:
        await _create_user(db, email="citizen@t.com", role="CITIZEN", eco_points=500, id=1)
        reward = Reward(id=1, title="Coffee", provider="Cafe", category="Food",
                        points_cost=100, is_active=1)
        db.add(reward)
        await db.commit()

    headers = await _auth(client, "citizen@t.com")
    resp = await client.post("/api/citizen/redeem_reward",
                             json={"reward_id": 1}, headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    assert data["remaining_points"] == 400, f"Expected 400 remaining, got {data['remaining_points']}"

    async with TestingSessionLocal() as db:
        result = await db.execute(select(User).filter(User.email == "citizen@t.com"))
        user = result.scalars().first()
        assert user.eco_points == 400


@pytest.mark.asyncio
async def test_redeem_reward_rejects_insufficient_points(client):
    async with TestingSessionLocal() as db:
        await _create_user(db, email="citizen@t.com", role="CITIZEN", eco_points=50, id=1)
        reward = Reward(id=1, title="Coffee", provider="Cafe", category="Food",
                        points_cost=100, is_active=1)
        db.add(reward)
        await db.commit()

    headers = await _auth(client, "citizen@t.com")
    resp = await client.post("/api/citizen/redeem_reward",
                             json={"reward_id": 1}, headers=headers)
    assert resp.status_code == 400, f"Should reject insufficient points, got {resp.status_code}"

    # Points must not have been deducted
    async with TestingSessionLocal() as db:
        result = await db.execute(select(User).filter(User.email == "citizen@t.com"))
        user = result.scalars().first()
        assert user.eco_points == 50, "Points must not change on failure"


@pytest.mark.asyncio
async def test_redeem_reward_prevents_negative_balance(client):
    """Rapid back-to-back redemption must not allow negative balance."""
    async with TestingSessionLocal() as db:
        await _create_user(db, email="citizen@t.com", role="CITIZEN", eco_points=100, id=1)
        reward = Reward(id=1, title="Coffee", provider="Cafe", category="Food",
                        points_cost=100, is_active=1)
        db.add(reward)
        await db.commit()

    headers = await _auth(client, "citizen@t.com")
    # First redemption should succeed
    resp1 = await client.post("/api/citizen/redeem_reward", json={"reward_id": 1}, headers=headers)
    assert resp1.status_code == 200

    # Second redemption of same reward must fail (no points left)
    resp2 = await client.post("/api/citizen/redeem_reward", json={"reward_id": 1}, headers=headers)
    assert resp2.status_code == 400, f"Second redemption should fail, got {resp2.status_code}"

    async with TestingSessionLocal() as db:
        result = await db.execute(select(User).filter(User.email == "citizen@t.com"))
        user = result.scalars().first()
        assert user.eco_points >= 0, f"Negative balance detected: {user.eco_points}"


# ─────────────────────────────────────────────
# Admin role enforcement
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_create_user_rejects_invalid_role(client):
    async with TestingSessionLocal() as db:
        await _create_user(db, email="admin@t.com", role="ADMIN")
    headers = await _auth(client, "admin@t.com")
    resp = await client.post("/api/admin/create_user",
                             json={"email": "x@t.com", "password": "p", "name": "X", "role": "SUPERUSER"},
                             headers=headers)
    assert resp.status_code == 422, f"Invalid role should be rejected, got {resp.status_code}"


@pytest.mark.asyncio
async def test_admin_create_user_rejects_duplicate_email(client):
    async with TestingSessionLocal() as db:
        await _create_user(db, email="admin@t.com", role="ADMIN")
        await _create_user(db, email="existing@t.com", role="CITIZEN")
    headers = await _auth(client, "admin@t.com")
    resp = await client.post("/api/admin/create_user",
                             json={"email": "existing@t.com", "password": "password", "name": "XY", "role": "CITIZEN"},
                             headers=headers)


    assert resp.status_code == 400, f"Duplicate email should be rejected, got {resp.status_code}"


# ─────────────────────────────────────────────
# Security: refresh token cannot be used as access token
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_refresh_token_rejected_as_access_token(client):
    async with TestingSessionLocal() as db:
        await _create_user(db, email="citizen@t.com", role="CITIZEN")

    login_resp = await client.post("/api/auth/login",
                                   data={"username": "citizen@t.com", "password": "password"})
    refresh_token = login_resp.json()["refresh_token"]

    headers = {"Authorization": f"Bearer {refresh_token}"}
    resp = await client.get("/api/citizen/dashboard", headers=headers)
    assert resp.status_code == 401, "Refresh token must be rejected as access token"
