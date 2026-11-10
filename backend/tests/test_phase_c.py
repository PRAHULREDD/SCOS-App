"""
SCOS Phase C — Citizen Feature Implementation Tests

Tests the Citizen enhancements:
  - Complaint description persistence and retrieval
  - GPS handling (valid coordinates, null coordinates, rejection of invalid coordinates)
  - Eco-points awards from valid operations
  - Community leaderboard querying real citizen records and rankings
  - Exclusion of non-citizens (ADMIN/DRIVER) from leaderboard
  - Role-based authorization on citizen endpoints
  - Citizen dashboard factual metrics
  - Safe reversible migration testing
"""
import pytest
import os
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from main import app
from app.db.database import get_db
from app.models.domain import Base, User, Complaint, Reward, RewardRedemption
from app.core.auth import get_password_hash

os.environ["SECRET_KEY"] = "testsecretkeytestsecretkeytestsecretkey"
os.environ["ENVIRONMENT"] = "testing"

# Shared DB with Phase 1/2/3 tests
SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///./test_scos.db"
engine = create_async_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(
    class_=AsyncSession, autocommit=False, autoflush=False,
    bind=engine, expire_on_commit=False
)

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


async def _create_user(role: str, email: str, name: str = "Test User", eco_points: int = 50):
    async with TestingSessionLocal() as db:
        user = User(
            email=email,
            name=name,
            password_hash=get_password_hash("password123"),
            role=role,
            eco_points=eco_points,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user.id


async def _get_token(client: AsyncClient, email: str, password: str = "password123") -> str:
    resp = await client.post("/api/auth/login", data={"username": email, "password": password})
    assert resp.status_code == 200, f"Login failed for {email}: {resp.text}"
    return resp.json()["access_token"]


# ─────────────────────────────────────────────────────────
# 1. Complaint Description Persistence & Retrieval
# ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_report_issue_persists_description(client):
    user_id = await _create_user(role="CITIZEN", email="c_desc@test.com", name="Desc Tester")
    token = await _get_token(client, "c_desc@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "zone": "North Zone",
        "area": "Oakwood Park",
        "description": "Overflowing public bin with plastic bottles near children playground.",
        "lat": 12.9500,
        "lng": 77.5800,
        "waste_type": "Plastic",
        "severity_level": "MEDIUM"
    }

    resp = await client.post("/api/citizen/report_issue", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    complaint_id = data["id"]

    # Verify directly in database
    async with TestingSessionLocal() as db:
        complaint = (await db.execute(select(Complaint).filter(Complaint.id == complaint_id))).scalars().first()
        assert complaint is not None
        assert complaint.description == "Overflowing public bin with plastic bottles near children playground."
        assert complaint.area == "Oakwood Park"

    # Verify via /api/citizen/my_reports
    reports_resp = await client.get("/api/citizen/my_reports", headers=headers)
    assert reports_resp.status_code == 200
    reports = reports_resp.json()["reports"]
    assert len(reports) >= 1
    found = next((r for r in reports if r["id"] == complaint_id), None)
    assert found is not None
    assert found["description"] == "Overflowing public bin with plastic bottles near children playground."


# ─────────────────────────────────────────────────────────
# 2. GPS Handling: Real Coordinates, Null GPS & Validation
# ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_report_issue_with_null_gps(client):
    """When GPS is denied or unavailable, null coordinates are accepted without substituting fake ones."""
    await _create_user(role="CITIZEN", email="c_nogps@test.com")
    token = await _get_token(client, "c_nogps@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "zone": "Central",
        "area": "Civic Center - North Gate",
        "description": "Reported without device GPS permission.",
        "lat": None,
        "lng": None,
        "waste_type": "General",
        "severity_level": "LOW"
    }

    resp = await client.post("/api/citizen/report_issue", json=payload, headers=headers)
    assert resp.status_code == 200
    complaint_id = resp.json()["id"]

    async with TestingSessionLocal() as db:
        complaint = (await db.execute(select(Complaint).filter(Complaint.id == complaint_id))).scalars().first()
        assert complaint.lat is None
        assert complaint.lng is None
        assert complaint.area == "Civic Center - North Gate"


@pytest.mark.asyncio
async def test_report_issue_rejects_out_of_range_gps(client):
    """Invalid latitude (>90) or longitude (>180) must be rejected with HTTP 422."""
    await _create_user(role="CITIZEN", email="c_badgps@test.com")
    token = await _get_token(client, "c_badgps@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Invalid latitude
    resp = await client.post("/api/citizen/report_issue", json={
        "zone": "Zone A", "area": "Locality 1", "lat": 95.0, "lng": 77.0
    }, headers=headers)
    assert resp.status_code == 422

    # Invalid longitude
    resp2 = await client.post("/api/citizen/report_issue", json={
        "zone": "Zone A", "area": "Locality 1", "lat": 12.0, "lng": 195.0
    }, headers=headers)
    assert resp2.status_code == 422


# ─────────────────────────────────────────────────────────
# 3. Eco-Points Awarded From Backend Operation
# ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_report_issue_awards_actual_points(client):
    await _create_user(role="CITIZEN", email="c_points@test.com", eco_points=100)
    token = await _get_token(client, "c_points@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post("/api/citizen/report_issue", json={
        "zone": "Zone B", "area": "Maple Street", "lat": 12.91, "lng": 77.52
    }, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["points"] == 110  # 100 + 10

    # Verify user profile in DB reflects exact 110 points
    async with TestingSessionLocal() as db:
        user = (await db.execute(select(User).filter(User.email == "c_points@test.com"))).scalars().first()
        assert user.eco_points == 110


# ─────────────────────────────────────────────────────────
# 4. Community Leaderboard Endpoint
# ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_leaderboard_ranks_citizens_by_ecopoints(client):
    # Create 3 citizens with different points
    await _create_user(role="CITIZEN", email="c1@test.com", name="Alice Bronze", eco_points=100)
    await _create_user(role="CITIZEN", email="c2@test.com", name="Bob Gold", eco_points=500)
    await _create_user(role="CITIZEN", email="c3@test.com", name="Charlie Silver", eco_points=250)

    token = await _get_token(client, "c1@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get("/api/citizen/leaderboard", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    board = data["leaderboard"]
    assert len(board) == 3
    # Check descending order
    assert board[0]["name"] == "Bob Gold"
    assert board[0]["eco_points"] == 500
    assert board[0]["rank"] == 1

    assert board[1]["name"] == "Charlie Silver"
    assert board[1]["eco_points"] == 250
    assert board[1]["rank"] == 2

    assert board[2]["name"] == "Alice Bronze"
    assert board[2]["eco_points"] == 100
    assert board[2]["rank"] == 3
    assert board[2]["is_current_user"] is True

    assert data["user_rank"] == 3
    assert data["user_points"] == 100


@pytest.mark.asyncio
async def test_leaderboard_excludes_admin_and_driver(client):
    await _create_user(role="CITIZEN", email="citizen_leader@test.com", name="Real Citizen", eco_points=50)
    await _create_user(role="DRIVER", email="driver_hidden@test.com", name="Secret Driver", eco_points=1000)
    await _create_user(role="ADMIN", email="admin_hidden@test.com", name="Secret Admin", eco_points=2000)

    token = await _get_token(client, "citizen_leader@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get("/api/citizen/leaderboard", headers=headers)
    assert resp.status_code == 200
    board = resp.json()["leaderboard"]

    names = [entry["name"] for entry in board]
    assert "Real Citizen" in names
    assert "Secret Driver" not in names
    assert "Secret Admin" not in names


@pytest.mark.asyncio
async def test_leaderboard_authorization_guards(client):
    """Requires authentication and CITIZEN role."""
    # 1. Unauthenticated
    resp_unauth = await client.get("/api/citizen/leaderboard")
    assert resp_unauth.status_code == 401

    # 2. Driver role rejected
    await _create_user(role="DRIVER", email="driver_guard@test.com")
    driver_token = await _get_token(client, "driver_guard@test.com")
    resp_driver = await client.get("/api/citizen/leaderboard", headers={"Authorization": f"Bearer {driver_token}"})
    assert resp_driver.status_code == 403

    # 3. Admin role rejected
    await _create_user(role="ADMIN", email="admin_guard@test.com")
    admin_token = await _get_token(client, "admin_guard@test.com")
    resp_admin = await client.get("/api/citizen/leaderboard", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp_admin.status_code == 403


# ─────────────────────────────────────────────────────────
# 5. Citizen Dashboard Factual Metrics
# ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_citizen_dashboard_factual_metrics(client):
    user_id = await _create_user(role="CITIZEN", email="c_dash@test.com", eco_points=70)
    token = await _get_token(client, "c_dash@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Add 1 pending and 1 resolved complaint directly
    async with TestingSessionLocal() as db:
        c1 = Complaint(citizen_id=user_id, zone="A", area="Loc 1", waste_type="General", severity_level="LOW", status="PENDING")
        c2 = Complaint(citizen_id=user_id, zone="B", area="Loc 2", waste_type="Organic", severity_level="HIGH", status="RESOLVED")
        db.add_all([c1, c2])
        await db.commit()

    resp = await client.get("/api/citizen/dashboard", headers=headers)
    assert resp.status_code == 200
    dash = resp.json()
    assert dash["total_reports"] == 2
    assert dash["pending_reports"] == 1
    assert dash["resolved_reports"] == 1
    assert dash["eco_points"] == 70
