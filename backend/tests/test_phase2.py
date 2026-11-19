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
from sqlalchemy import func

from main import app
from app.db.database import get_db
from app.models.domain import Base, User, Complaint, DriverTask, DriverLocation, Reward, RewardRedemption, DumpingIncident
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
        await _create_user(db, email="existing@t.com", role="DRIVER")
    headers = await _auth(client, "admin@t.com")
    resp = await client.post("/api/admin/create_user",
                             json={"email": "existing@t.com", "password": "password", "name": "XY", "role": "DRIVER"},
                             headers=headers)
    assert resp.status_code == 400, f"Duplicate email should be rejected, got {resp.status_code}"


@pytest.mark.asyncio
async def test_admin_create_user_rejects_citizen_role(client):
    async with TestingSessionLocal() as db:
        await _create_user(db, email="admin@t.com", role="ADMIN")
    headers = await _auth(client, "admin@t.com")
    resp = await client.post("/api/admin/create_user",
                             json={"email": "citizen_candidate@t.com", "password": "password", "name": "Citizen Candidate", "role": "CITIZEN"},
                             headers=headers)
    assert resp.status_code == 422, f"Admin must not create CITIZEN accounts, got {resp.status_code}"


@pytest.mark.asyncio
async def test_admin_create_user_rejects_admin_role(client):
    async with TestingSessionLocal() as db:
        await _create_user(db, email="admin@t.com", role="ADMIN")
    headers = await _auth(client, "admin@t.com")
    resp = await client.post("/api/admin/create_user",
                             json={"email": "subadmin@t.com", "password": "password", "name": "Sub Admin", "role": "ADMIN"},
                             headers=headers)
    assert resp.status_code == 422, f"Admin must not create ADMIN accounts, got {resp.status_code}"


@pytest.mark.asyncio
async def test_admin_overview_omits_contractors(client):
    async with TestingSessionLocal() as db:
        await _create_user(db, email="admin@t.com", role="ADMIN")
    headers = await _auth(client, "admin@t.com")
    resp = await client.get("/api/admin/overview", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "top_contractors" not in data, "Contractor analytics must be removed from overview"
    assert "total_complaints" in data
    assert "pending_complaints" in data
    assert "collection_rate" in data


@pytest.mark.asyncio
async def test_admin_illegal_dumping_omits_fake_clear_time(client):
    async with TestingSessionLocal() as db:
        await _create_user(db, email="admin@t.com", role="ADMIN")
    headers = await _auth(client, "admin@t.com")
    resp = await client.get("/api/admin/illegal_dumping", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "avg_clear_time" not in data, "Fake clearance time must be removed"
    assert "avg_clear_hours" not in data, "Fake clearance time must be removed"
    assert "active_count" in data
    assert "incidents" in data


@pytest.mark.asyncio
async def test_admin_waste_heatmap_returns_complaint_coords(client):
    async with TestingSessionLocal() as db:
        await _create_user(db, email="admin@t.com", role="ADMIN")
        c1 = Complaint(id=101, citizen_id=1, zone="North", area="Main St", waste_type="Plastic",
                       severity_level="HIGH", status="PENDING", lat=12.9123, lng=77.5432)
        c2 = Complaint(id=102, citizen_id=1, zone="South", area="Park Ave", waste_type="Organic",
                       severity_level="MEDIUM", status="RESOLVED", lat=12.9456, lng=77.5876)
        db.add_all([c1, c2])
        await db.commit()

    headers = await _auth(client, "admin@t.com")
    resp = await client.get("/api/admin/waste_heatmap", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "heatmap_points" in data
    assert data["total"] >= 2
    points = data["heatmap_points"]
    assert any(p["lat"] == 12.9123 and p["lng"] == 77.5432 for p in points)


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


# ─────────────────────────────────────────────
# High-Priority Queue Sanitization Tests
# Target: GET /api/admin/illegal_dumping
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_illegal_dumping_severity_and_status_filtering(client):
    """
    Invariants covered:
    1. HIGH complaints are returned.
    2. CRITICAL complaints are returned.
    3. MEDIUM complaints are excluded.
    4. LOW complaints are excluded.
    5. RESOLVED HIGH/CRITICAL complaints are excluded.
    8. active_count equals the number of returned complaints.
    9. active_incidents equals the number of returned complaints.
    10. high_risk_count equals the number of returned HIGH/CRITICAL complaints.
    """
    crit_id, high_id, med_id, low_id = 101, 102, 103, 104
    resolved_high_id, resolved_crit_id = 105, 106

    async with TestingSessionLocal() as db:
        await _create_user(db, email="admin_queue@t.com", role="ADMIN", id=91)
        await _create_user(db, email="citizen_queue@t.com", role="CITIZEN", id=1)

        c_critical_pending = Complaint(
            id=crit_id, citizen_id=1, zone="North", area="Industrial Sector 1",
            waste_type="Chemical", severity_level="CRITICAL", status="PENDING",
            lat=12.91, lng=77.51, description="Critical chemical spill"
        )
        c_high_pending = Complaint(
            id=high_id, citizen_id=1, zone="South", area="Residential Sector 4",
            waste_type="Plastic", severity_level="HIGH", status="PENDING",
            lat=12.92, lng=77.52, description="Severe plastic blockage"
        )
        c_medium_pending = Complaint(
            id=med_id, citizen_id=1, zone="East", area="Commercial Sector 2",
            waste_type="Organic", severity_level="MEDIUM", status="PENDING",
            lat=12.93, lng=77.53, description="Medium organic waste"
        )
        c_low_pending = Complaint(
            id=low_id, citizen_id=1, zone="West", area="Market Sector 5",
            waste_type="Paper", severity_level="LOW", status="PENDING",
            lat=12.94, lng=77.54, description="Low paper litter"
        )
        c_high_resolved = Complaint(
            id=resolved_high_id, citizen_id=1, zone="Central", area="Metro Hub",
            waste_type="Electronic", severity_level="HIGH", status="RESOLVED",
            lat=12.95, lng=77.55, description="Resolved high e-waste"
        )
        c_critical_resolved = Complaint(
            id=resolved_crit_id, citizen_id=1, zone="Central", area="Main Square",
            waste_type="Hazardous", severity_level="CRITICAL", status="RESOLVED",
            lat=12.96, lng=77.56, description="Resolved critical hazard"
        )

        db.add_all([
            c_critical_pending, c_high_pending,
            c_medium_pending, c_low_pending,
            c_high_resolved, c_critical_resolved
        ])
        await db.commit()

    headers = await _auth(client, "admin_queue@t.com")
    resp = await client.get("/api/admin/illegal_dumping", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    returned_items = data.get("incidents", [])
    returned_ids = [item["id"] for item in returned_items]

    # 1. HIGH complaints are returned
    assert high_id in returned_ids, f"HIGH pending complaint {high_id} must be included"
    # 2. CRITICAL complaints are returned
    assert crit_id in returned_ids, f"CRITICAL pending complaint {crit_id} must be included"
    # 3. MEDIUM complaints are excluded
    assert med_id not in returned_ids, f"MEDIUM complaint {med_id} must be excluded"
    # 4. LOW complaints are excluded
    assert low_id not in returned_ids, f"LOW complaint {low_id} must be excluded"
    # 5. RESOLVED HIGH/CRITICAL complaints are excluded
    assert resolved_high_id not in returned_ids, f"RESOLVED HIGH complaint {resolved_high_id} must be excluded"
    assert resolved_crit_id not in returned_ids, f"RESOLVED CRITICAL complaint {resolved_crit_id} must be excluded"

    # Total returned complaints should be exactly 2
    assert len(returned_items) == 2

    # 8. active_count equals the number of returned complaints
    assert data["active_count"] == 2
    # 9. active_incidents equals the number of returned complaints
    assert data["active_incidents"] == 2
    # 10. high_risk_count equals the number of returned HIGH/CRITICAL complaints
    assert data["high_risk_count"] == 2


@pytest.mark.asyncio
async def test_admin_illegal_dumping_excludes_active_dumping_incidents(client):
    """
    Invariant 6: Active legacy DumpingIncident records are not returned.
    """
    valid_cid = 101
    inc1_id = 201
    inc2_id = 202

    async with TestingSessionLocal() as db:
        await _create_user(db, email="admin_inc@t.com", role="ADMIN", id=92)
        await _create_user(db, email="citizen_inc@t.com", role="CITIZEN", id=1)

        # 1 valid high-priority complaint with explicit ID
        valid_complaint = Complaint(
            id=valid_cid, citizen_id=1, zone="East Sector", area="Harbor",
            waste_type="Industrial", severity_level="HIGH", status="PENDING",
            lat=13.01, lng=77.61, description="Active high complaint"
        )
        db.add(valid_complaint)

        # 2 active legacy dumping incidents with distinct IDs
        legacy_inc1 = DumpingIncident(
            id=inc1_id, zone="Legacy Zone Alpha", cluster_id="CL-01",
            description="Legacy critical dump incident", severity="CRITICAL",
            status="ACTIVE", lat=13.05, lng=77.65
        )
        legacy_inc2 = DumpingIncident(
            id=inc2_id, zone="Legacy Zone Beta", cluster_id="CL-02",
            description="Legacy high dump incident", severity="HIGH",
            status="ACTIVE", lat=13.06, lng=77.66
        )
        db.add_all([legacy_inc1, legacy_inc2])
        await db.commit()

    headers = await _auth(client, "admin_inc@t.com")
    resp = await client.get("/api/admin/illegal_dumping", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    returned_items = data.get("incidents", [])
    returned_ids = [item["id"] for item in returned_items]

    # Valid complaint is present
    assert valid_cid in returned_ids
    # Legacy dumping incidents are NOT returned
    assert inc1_id not in returned_ids
    assert inc2_id not in returned_ids
    assert not any(i["description"] == "Legacy critical dump incident" for i in returned_items)
    assert not any(i["description"] == "Legacy high dump incident" for i in returned_items)
    assert not any(i.get("waste_type") == "Illegal Dumping" for i in returned_items)

    assert len(returned_items) == 1
    assert data["active_count"] == 1
    assert data["active_incidents"] == 1
    assert data["high_risk_count"] == 1


@pytest.mark.asyncio
async def test_admin_illegal_dumping_id_collision_safety(client):
    """
    Invariant 7: Identical IDs in Complaint and DumpingIncident cannot cause
    a legacy record to appear in the queue.
    """
    COLLISION_ID = 555
    async with TestingSessionLocal() as db:
        await _create_user(db, email="admin_coll@t.com", role="ADMIN", id=93)
        await _create_user(db, email="citizen_coll@t.com", role="CITIZEN", id=1)

        # Explicitly construct a Complaint with ID=555 and severity=LOW (must be excluded)
        c_low_colliding = Complaint(
            id=COLLISION_ID, citizen_id=1, zone="Sector 9", area="Colliding Road",
            waste_type="Paper", severity_level="LOW", status="PENDING",
            lat=12.11, lng=77.11, description="Citizen low complaint with colliding id"
        )
        # Explicitly construct a DumpingIncident with ID=555 and severity=CRITICAL, status=ACTIVE
        inc_colliding = DumpingIncident(
            id=COLLISION_ID, zone="Sector 9", cluster_id="COLL-01",
            description="Legacy incident with colliding id", severity="CRITICAL",
            status="ACTIVE", lat=12.12, lng=77.12
        )
        # Legitimate high priority complaint with different ID
        c_high_legit = Complaint(
            id=777, citizen_id=1, zone="Sector 10", area="Clear Road",
            waste_type="Hazardous", severity_level="CRITICAL", status="PENDING",
            lat=12.13, lng=77.13, description="Legitimate critical complaint"
        )

        db.add_all([c_low_colliding, inc_colliding, c_high_legit])
        await db.commit()

    headers = await _auth(client, "admin_coll@t.com")
    resp = await client.get("/api/admin/illegal_dumping", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    returned_items = data.get("incidents", [])
    returned_ids = [item["id"] for item in returned_items]

    # Collision ID 555 must NOT appear in the response:
    # - The Complaint with ID 555 has severity LOW (excluded)
    # - The DumpingIncident with ID 555 must not be queried or returned
    assert COLLISION_ID not in returned_ids
    assert not any(i["description"] == "Legacy incident with colliding id" for i in returned_items)
    assert not any(i["description"] == "Citizen low complaint with colliding id" for i in returned_items)

    # Only Complaint 777 appears
    assert 777 in returned_ids
    assert len(returned_items) == 1
    assert returned_items[0]["description"] == "Legitimate critical complaint"


@pytest.mark.asyncio
async def test_admin_illegal_dumping_valid_complaint_assignment_flow(client):
    """
    Invariant 11: Valid Complaint assignment continues to work from queue-sourced IDs.
    """
    driver_id = 24
    assigned_cid = 301

    async with TestingSessionLocal() as db:
        await _create_user(db, email="admin_assign@t.com", role="ADMIN", id=94)
        await _create_user(db, email="driver_assign@t.com", role="DRIVER", name="Assigned Driver", id=driver_id)
        await _create_user(db, email="citizen_assign@t.com", role="CITIZEN", id=1)

        complaint = Complaint(
            id=assigned_cid, citizen_id=1, zone="North Sector", area="Freight Terminal",
            waste_type="Industrial", severity_level="HIGH", status="PENDING",
            lat=13.10, lng=77.70, description="Industrial waste accumulation"
        )
        db.add(complaint)
        await db.commit()

    admin_headers = await _auth(client, "admin_assign@t.com")

    # 1. Fetch from high priority queue
    queue_resp = await client.get("/api/admin/illegal_dumping", headers=admin_headers)
    assert queue_resp.status_code == 200
    queue_items = queue_resp.json()["incidents"]
    assert any(item["id"] == assigned_cid for item in queue_items)

    # 2. Assign driver via POST /api/admin/assign_task
    assign_resp = await client.post(
        "/api/admin/assign_task",
        json={
            "complaint_id": assigned_cid,
            "driver_id": driver_id,
            "waste_type": "Industrial",
            "address": "Freight Terminal, North Sector"
        },
        headers=admin_headers
    )
    assert assign_resp.status_code == 200, assign_resp.text
    assign_data = assign_resp.json()
    assert "task_id" in assign_data
    assert assign_data["task_id"] > 0

    # 3. Verify Complaint status transitioned to IN_PROGRESS in database
    async with TestingSessionLocal() as db:
        updated_c = await db.get(Complaint, assigned_cid)
        assert updated_c.status == "IN_PROGRESS"


@pytest.mark.asyncio
async def test_admin_illegal_dumping_in_progress_monitoring_queue(client):
    """
    Requirement B: Verify that an IN_PROGRESS HIGH or CRITICAL complaint:
    - Appears in the monitoring queue.
    - Retains its IN_PROGRESS status.
    - Is not treated as a new assignable task (re-assignment rejected with HTTP 409 Conflict).
    """
    inp_cid = 401
    pen_cid = 402
    driver_id = 25

    async with TestingSessionLocal() as db:
        await _create_user(db, email="admin_inp@t.com", role="ADMIN", id=95)
        await _create_user(db, email="driver_inp@t.com", role="DRIVER", name="Driver Inp", id=driver_id)
        await _create_user(db, email="citizen_inp@t.com", role="CITIZEN", id=1)

        c_inp = Complaint(
            id=inp_cid, citizen_id=1, zone="Industrial North", area="Terminal 1",
            waste_type="Chemical", severity_level="CRITICAL", status="IN_PROGRESS",
            lat=12.98, lng=77.58, description="In progress critical spill"
        )
        c_pen = Complaint(
            id=pen_cid, citizen_id=1, zone="Commercial South", area="Plaza 4",
            waste_type="Industrial", severity_level="HIGH", status="PENDING",
            lat=12.99, lng=77.59, description="Pending high waste report"
        )
        task_inp = DriverTask(
            id=501, driver_id=driver_id, complaint_id=inp_cid, priority="CRITICAL",
            waste_type="Chemical", address="Terminal 1", status="ASSIGNED"
        )
        db.add_all([c_inp, c_pen, task_inp])
        await db.commit()

    admin_headers = await _auth(client, "admin_inp@t.com")

    # 1. Verify both appear in monitoring queue
    resp = await client.get("/api/admin/illegal_dumping", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    items = data.get("incidents", [])
    returned_ids = [item["id"] for item in items]

    assert inp_cid in returned_ids, "IN_PROGRESS critical complaint must appear in monitoring queue"
    assert pen_cid in returned_ids, "PENDING high complaint must appear in monitoring queue"

    # 2. Verify status retention
    inp_item = next(item for item in items if item["id"] == inp_cid)
    pen_item = next(item for item in items if item["id"] == pen_cid)
    assert inp_item["status"] == "IN_PROGRESS", "Must retain IN_PROGRESS status in queue"
    assert pen_item["status"] == "PENDING", "Must retain PENDING status in queue"

    # Both are counted in active / high-risk metrics
    assert data["active_count"] == 2
    assert data["high_risk_count"] == 2

    # 3. Attempting to assign the IN_PROGRESS complaint must fail with 409 Conflict
    reassign_resp = await client.post(
        "/api/admin/assign_task",
        json={
            "complaint_id": inp_cid,
            "driver_id": driver_id,
            "waste_type": "Chemical",
            "address": "Terminal 1"
        },
        headers=admin_headers
    )
    assert reassign_resp.status_code == 409, (
        f"Expected 409 Conflict when assigning an IN_PROGRESS complaint, got {reassign_resp.status_code}"
    )
    assert "cannot be assigned in state 'IN_PROGRESS'" in reassign_resp.json()["detail"]

    # 4. Verify no new task was created and complaint status is unchanged
    async with TestingSessionLocal() as db:
        stmt = select(func.count()).select_from(DriverTask).where(DriverTask.complaint_id == inp_cid)
        task_count = (await db.execute(stmt)).scalar()
        assert task_count == 1, "No additional DriverTask may be created"

        c_check = await db.get(Complaint, inp_cid)
        assert c_check.status == "IN_PROGRESS"


@pytest.mark.asyncio
async def test_admin_assign_task_rejects_legacy_incident_id(client):
    """
    Requirement C: Create a DumpingIncident with a known ID for which no Complaint exists.
    Attempt to assign that ID through POST /api/admin/assign_task.
    Verify:
    - HTTP 404.
    - No DriverTask is created.
    - No unrelated Complaint is modified.
    """
    LEGACY_ID = 8888
    driver_id = 26
    unrelated_cid = 50

    async with TestingSessionLocal() as db:
        await _create_user(db, email="admin_legacy@t.com", role="ADMIN", id=96)
        await _create_user(db, email="driver_legacy@t.com", role="DRIVER", name="Driver Legacy", id=driver_id)
        await _create_user(db, email="citizen_legacy@t.com", role="CITIZEN", id=1)

        # Unrelated Complaint
        c_unrelated = Complaint(
            id=unrelated_cid, citizen_id=1, zone="Residential", area="Maple St",
            waste_type="General", severity_level="MEDIUM", status="PENDING",
            description="Unrelated medium report"
        )
        # Legacy DumpingIncident with known ID 8888; NO Complaint with ID 8888 exists
        inc_legacy = DumpingIncident(
            id=LEGACY_ID, zone="Surveillance Sector", cluster_id="SURV-99",
            description="Legacy dumping camera hit", severity="CRITICAL",
            status="ACTIVE", lat=12.80, lng=77.40
        )
        db.add_all([c_unrelated, inc_legacy])
        await db.commit()

        # Confirm no complaint exists with LEGACY_ID
        c_legacy_check = await db.get(Complaint, LEGACY_ID)
        assert c_legacy_check is None, "Precondition failed: Complaint 8888 must not exist"

        # Baseline count of DriverTask
        task_count_before = (await db.execute(select(func.count()).select_from(DriverTask))).scalar() or 0

    admin_headers = await _auth(client, "admin_legacy@t.com")

    # Attempt to assign the legacy incident ID
    resp = await client.post(
        "/api/admin/assign_task",
        json={
            "complaint_id": LEGACY_ID,
            "driver_id": driver_id,
            "waste_type": "Hazardous",
            "address": "Surveillance Sector"
        },
        headers=admin_headers
    )

    # 1. Verify HTTP 404
    assert resp.status_code == 404, f"Expected 404 when assigning legacy incident ID, got {resp.status_code}"
    assert resp.json()["detail"] == "Complaint not found"

    # 2. Verify no DriverTask is created
    # 3. Verify no unrelated Complaint is modified
    async with TestingSessionLocal() as db:
        task_count_after = (await db.execute(select(func.count()).select_from(DriverTask))).scalar() or 0
        assert task_count_after == task_count_before, "No DriverTask must be created"

        c_after = await db.get(Complaint, unrelated_cid)
        assert c_after.status == "PENDING", "Unrelated complaint status must remain PENDING"
        assert c_after.description == "Unrelated medium report", "Unrelated complaint description must not be altered"

        inc_after = await db.get(DumpingIncident, LEGACY_ID)
        assert inc_after.status == "ACTIVE", "Legacy incident record must remain intact"


@pytest.mark.asyncio
async def test_admin_illegal_dumping_role_and_auth_guards(client):
    """
    Invariants 12 & 13:
    12. Citizen and Driver roles receive HTTP 403 when accessing the endpoint.
    13. Unauthenticated requests remain rejected (HTTP 401).
    """
    async with TestingSessionLocal() as db:
        await _create_user(db, email="citizen_guard@t.com", role="CITIZEN", id=1)
        await _create_user(db, email="driver_guard@t.com", role="DRIVER", id=27)

    # 13. Unauthenticated request rejected with 401
    resp_unauth = await client.get("/api/admin/illegal_dumping")
    assert resp_unauth.status_code == 401, f"Expected 401 for unauthenticated request, got {resp_unauth.status_code}"

    # 12. Citizen token rejected with 403
    citizen_headers = await _auth(client, "citizen_guard@t.com")
    resp_citizen = await client.get("/api/admin/illegal_dumping", headers=citizen_headers)
    assert resp_citizen.status_code == 403, f"Expected 403 for CITIZEN role, got {resp_citizen.status_code}"

    # 12. Driver token rejected with 403
    driver_headers = await _auth(client, "driver_guard@t.com")
    resp_driver = await client.get("/api/admin/illegal_dumping", headers=driver_headers)
    assert resp_driver.status_code == 403, f"Expected 403 for DRIVER role, got {resp_driver.status_code}"
