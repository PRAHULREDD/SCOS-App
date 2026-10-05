"""
SCOS Phase 3 — Core Demo Flow Integration Tests

Tests the complete end-to-end workflow:
  Citizen creates complaint
  → Admin retrieves complaint
  → Admin assigns driver
  → Driver retrieves task
  → Driver completes pickup
  → Complaint/assignment status updated correctly

Also verifies all authorization guard scenarios.
"""
import pytest
import os
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from main import app
from app.db.database import get_db
from app.models.domain import Base, User, Complaint, DriverTask
from app.core.auth import get_password_hash

os.environ["SECRET_KEY"] = "testsecretkeytestsecretkeytestsecretkey"
os.environ["ENVIRONMENT"] = "testing"

# Shared DB with Phase 1/2 tests
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


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

async def _create_user(role: str, email: str = None, name: str = "Test User"):
    """Insert a user directly into the test DB."""
    if email is None:
        email = f"{role.lower()}@test.com"
    async with TestingSessionLocal() as db:
        user = User(
            email=email,
            name=name,
            password_hash=get_password_hash("password"),
            role=role,
            eco_points=50,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user.id


async def _login(client, email: str, password: str = "password") -> str:
    """Login and return the Bearer token."""
    form_data = {"username": email, "password": password}
    resp = await client.post("/api/auth/login", data=form_data)
    assert resp.status_code == 200, f"Login failed for {email}: {resp.text}"
    return resp.json()["access_token"]


async def _headers(client, email: str) -> dict:
    token = await _login(client, email)
    return {"Authorization": f"Bearer {token}"}


# ─────────────────────────────────────────────
# Test 1: Citizen creates complaint
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_citizen_creates_complaint(client):
    """Citizen can submit a waste report and it is persisted."""
    await _create_user("CITIZEN", "citizen@test.com")
    h = await _headers(client, "citizen@test.com")

    resp = await client.post(
        "/api/citizen/report_issue",
        json={
            "zone": "Zone A",
            "area": "Main Street",
            "lat": 12.97,
            "lng": 77.59,
            "waste_type": "Organic",
            "severity_level": "HIGH",
        },
        headers=h
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "id" in data, "Response must include complaint id"
    assert data["id"] > 0
    assert "points" in data


# ─────────────────────────────────────────────
# Test 2: Admin retrieves complaint
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_retrieves_complaint(client):
    """After citizen reports, admin can see it in /api/admin/complaints."""
    await _create_user("CITIZEN", "citizen@test.com")
    await _create_user("ADMIN", "admin@test.com")

    citizen_h = await _headers(client, "citizen@test.com")
    admin_h = await _headers(client, "admin@test.com")

    # Citizen creates a complaint
    create_resp = await client.post(
        "/api/citizen/report_issue",
        json={"zone": "Zone B", "area": "Park Road", "lat": 12.9, "lng": 77.5,
              "waste_type": "Plastic", "severity_level": "MEDIUM"},
        headers=citizen_h
    )
    assert create_resp.status_code == 200
    complaint_id = create_resp.json()["id"]

    # Admin retrieves all complaints
    list_resp = await client.get("/api/admin/complaints", headers=admin_h)
    assert list_resp.status_code == 200, list_resp.text
    data = list_resp.json()
    assert "complaints" in data
    ids = [c["id"] for c in data["complaints"]]
    assert complaint_id in ids, f"Complaint {complaint_id} not found in admin list"

    # Verify complaint data integrity
    complaint = next(c for c in data["complaints"] if c["id"] == complaint_id)
    assert complaint["status"] == "PENDING"
    assert complaint["area"] == "Park Road"
    assert complaint["waste_type"] == "Plastic"


# ─────────────────────────────────────────────
# Test 3: Admin assigns driver
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_assigns_driver(client):
    """Admin can assign a driver to a complaint; DriverTask and Complaint.status updated."""
    citizen_id = await _create_user("CITIZEN", "citizen@test.com")
    driver_id = await _create_user("DRIVER", "driver@test.com", name="Driver One")
    await _create_user("ADMIN", "admin@test.com")

    citizen_h = await _headers(client, "citizen@test.com")
    admin_h = await _headers(client, "admin@test.com")

    # Citizen creates complaint
    create_resp = await client.post(
        "/api/citizen/report_issue",
        json={"zone": "Zone C", "area": "River Bank", "lat": 12.8, "lng": 77.4,
              "waste_type": "General", "severity_level": "LOW"},
        headers=citizen_h
    )
    complaint_id = create_resp.json()["id"]

    # Admin assigns driver
    assign_resp = await client.post(
        "/api/admin/assign_task",
        json={
            "complaint_id": complaint_id,
            "driver_id": driver_id,
            "waste_type": "General",
            "address": "River Bank, Zone C",
        },
        headers=admin_h
    )
    assert assign_resp.status_code == 200, assign_resp.text
    assign_data = assign_resp.json()
    assert "task_id" in assign_data
    task_id = assign_data["task_id"]
    assert task_id > 0

    # Verify complaint status changed to IN_PROGRESS
    complaint_list = await client.get("/api/admin/complaints", headers=admin_h)
    complaints = complaint_list.json()["complaints"]
    complaint = next(c for c in complaints if c["id"] == complaint_id)
    assert complaint["status"] == "IN_PROGRESS", (
        f"Complaint should be IN_PROGRESS after assignment, got {complaint['status']}"
    )


# ─────────────────────────────────────────────
# Test 4: Driver retrieves assigned task
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_driver_retrieves_assigned_task(client):
    """Driver can see their assigned task in /api/driver/assigned_tasks."""
    await _create_user("CITIZEN", "citizen@test.com")
    driver_id = await _create_user("DRIVER", "driver@test.com", name="Driver Two")
    await _create_user("ADMIN", "admin@test.com")

    citizen_h = await _headers(client, "citizen@test.com")
    driver_h = await _headers(client, "driver@test.com")
    admin_h = await _headers(client, "admin@test.com")

    # Setup: citizen reports, admin assigns
    report = await client.post(
        "/api/citizen/report_issue",
        json={"zone": "Zone D", "area": "Bus Stand", "lat": 12.7, "lng": 77.3,
              "waste_type": "Hazardous", "severity_level": "HIGH"},
        headers=citizen_h
    )
    complaint_id = report.json()["id"]

    await client.post(
        "/api/admin/assign_task",
        json={"complaint_id": complaint_id, "driver_id": driver_id,
              "waste_type": "Hazardous", "address": "Bus Stand, Zone D"},
        headers=admin_h
    )

    # Driver retrieves assigned tasks
    tasks_resp = await client.get("/api/driver/assigned_tasks", headers=driver_h)
    assert tasks_resp.status_code == 200, tasks_resp.text
    tasks = tasks_resp.json()["tasks"]
    assert len(tasks) > 0, "Driver should have at least one assigned task"

    task = next((t for t in tasks if t["complaint_id"] == complaint_id), None)
    assert task is not None, f"Task for complaint {complaint_id} not found in driver's tasks"
    assert task["status"] == "ASSIGNED"
    assert task["driver_id"] == driver_id


# ─────────────────────────────────────────────
# Test 5 & 6: Driver completes pickup, status updates
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_driver_completes_pickup_updates_status(client):
    """
    Driver completes pickup:
    - DriverTask.status → COMPLETED
    - Complaint.status → RESOLVED
    """
    await _create_user("CITIZEN", "citizen@test.com")
    driver_id = await _create_user("DRIVER", "driver@test.com", name="Driver Three")
    await _create_user("ADMIN", "admin@test.com")

    citizen_h = await _headers(client, "citizen@test.com")
    driver_h = await _headers(client, "driver@test.com")
    admin_h = await _headers(client, "admin@test.com")

    # Citizen reports
    report = await client.post(
        "/api/citizen/report_issue",
        json={"zone": "Zone E", "area": "Market", "lat": 12.6, "lng": 77.2,
              "waste_type": "Organic", "severity_level": "MEDIUM"},
        headers=citizen_h
    )
    complaint_id = report.json()["id"]

    # Admin assigns
    assign = await client.post(
        "/api/admin/assign_task",
        json={"complaint_id": complaint_id, "driver_id": driver_id,
              "waste_type": "Organic", "address": "Market, Zone E"},
        headers=admin_h
    )
    assert assign.status_code == 200

    # Driver completes pickup (no photo required)
    complete_resp = await client.post(
        "/api/driver/complete_pickup",
        data={"complaint_id": str(complaint_id)},
        headers=driver_h
    )
    assert complete_resp.status_code == 200, complete_resp.text
    complete_data = complete_resp.json()
    assert "task_id" in complete_data

    # Verify complaint is RESOLVED
    complaints = (await client.get("/api/admin/complaints", headers=admin_h)).json()["complaints"]
    complaint = next(c for c in complaints if c["id"] == complaint_id)
    assert complaint["status"] == "RESOLVED", (
        f"Complaint should be RESOLVED after driver completes, got {complaint['status']}"
    )

    # Verify driver task is COMPLETED
    tasks = (await client.get("/api/driver/assigned_tasks", headers=driver_h)).json()["tasks"]
    task = next((t for t in tasks if t["complaint_id"] == complaint_id), None)
    assert task is not None
    assert task["status"] == "COMPLETED", (
        f"Task should be COMPLETED, got {task['status']}"
    )


# ─────────────────────────────────────────────
# Test 7: Unauthorized roles cannot perform protected actions
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_unauthorized_roles_rejected(client):
    """Citizen cannot assign tasks; driver cannot access admin endpoints."""
    citizen_id = await _create_user("CITIZEN", "citizen@test.com")
    driver_id = await _create_user("DRIVER", "driver@test.com")

    citizen_h = await _headers(client, "citizen@test.com")
    driver_h = await _headers(client, "driver@test.com")

    # Citizen cannot call assign_task
    resp = await client.post(
        "/api/admin/assign_task",
        json={"complaint_id": 1, "driver_id": driver_id, "waste_type": "X", "address": "Y"},
        headers=citizen_h
    )
    assert resp.status_code == 403, f"Citizen should get 403, got {resp.status_code}"

    # Citizen cannot list admin complaints
    resp2 = await client.get("/api/admin/complaints", headers=citizen_h)
    assert resp2.status_code == 403

    # Driver cannot call admin endpoints
    resp3 = await client.post(
        "/api/admin/assign_task",
        json={"complaint_id": 1, "driver_id": driver_id, "waste_type": "X", "address": "Y"},
        headers=driver_h
    )
    assert resp3.status_code == 403

    # Unauthenticated request rejected
    resp4 = await client.get("/api/admin/complaints")
    assert resp4.status_code == 401


# ─────────────────────────────────────────────
# Test 8: Driver cannot complete another driver's task
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_driver_cannot_complete_other_drivers_task(client):
    """Driver B cannot complete a task assigned to Driver A."""
    await _create_user("CITIZEN", "citizen@test.com")
    driver_a_id = await _create_user("DRIVER", "driver_a@test.com", name="Driver A")
    await _create_user("DRIVER", "driver_b@test.com", name="Driver B")
    await _create_user("ADMIN", "admin@test.com")

    citizen_h = await _headers(client, "citizen@test.com")
    driver_b_h = await _headers(client, "driver_b@test.com")
    admin_h = await _headers(client, "admin@test.com")

    # Citizen reports
    report = await client.post(
        "/api/citizen/report_issue",
        json={"zone": "Zone F", "area": "School", "lat": 12.5, "lng": 77.1,
              "waste_type": "General", "severity_level": "LOW"},
        headers=citizen_h
    )
    complaint_id = report.json()["id"]

    # Admin assigns to Driver A
    await client.post(
        "/api/admin/assign_task",
        json={"complaint_id": complaint_id, "driver_id": driver_a_id,
              "waste_type": "General", "address": "School, Zone F"},
        headers=admin_h
    )

    # Driver B attempts to complete Driver A's task
    resp = await client.post(
        "/api/driver/complete_pickup",
        data={"complaint_id": str(complaint_id)},
        headers=driver_b_h
    )
    assert resp.status_code == 404, (
        f"Driver B should get 404 for another driver's task, got {resp.status_code}: {resp.text}"
    )


# ─────────────────────────────────────────────
# Test 9: Admin /drivers endpoint lists driver users
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_list_drivers(client):
    """Admin can retrieve the list of registered drivers."""
    await _create_user("DRIVER", "d1@test.com", name="Alice Driver")
    await _create_user("DRIVER", "d2@test.com", name="Bob Driver")
    await _create_user("CITIZEN", "c1@test.com")
    await _create_user("ADMIN", "admin@test.com")

    admin_h = await _headers(client, "admin@test.com")
    resp = await client.get("/api/admin/drivers", headers=admin_h)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "drivers" in data
    names = [d["name"] for d in data["drivers"]]
    assert "Alice Driver" in names
    assert "Bob Driver" in names
    # Citizens should NOT appear
    emails = [d["email"] for d in data["drivers"]]
    assert "c1@test.com" not in emails


# ─────────────────────────────────────────────
# Test 10: Full demo scenario end-to-end (sequence)
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_full_demo_flow(client):
    """
    Runs the complete demo sequence as a single test:
    1. Citizen logs in
    2. Citizen raises waste issue
    3. Admin sees issue (PENDING)
    4. Admin assigns driver
    5. Complaint becomes IN_PROGRESS
    6. Driver sees assigned task
    7. Driver completes pickup
    8. Complaint → RESOLVED, Task → COMPLETED
    """
    # Setup
    await _create_user("CITIZEN", "citizen@demo.com", "Demo Citizen")
    driver_id = await _create_user("DRIVER", "driver@demo.com", "Demo Driver")
    await _create_user("ADMIN", "admin@demo.com", "Demo Admin")

    citizen_h = await _headers(client, "citizen@demo.com")
    driver_h = await _headers(client, "driver@demo.com")
    admin_h = await _headers(client, "admin@demo.com")

    # Step 1 & 2: Citizen raises issue
    report = await client.post(
        "/api/citizen/report_issue",
        json={"zone": "Demo Zone", "area": "Demo Street",
              "lat": 12.9716, "lng": 77.5946,
              "waste_type": "Mixed", "severity_level": "HIGH"},
        headers=citizen_h
    )
    assert report.status_code == 200, f"Report failed: {report.text}"
    complaint_id = report.json()["id"]

    # Step 3: Admin sees PENDING complaint
    complaints = (await client.get("/api/admin/complaints", headers=admin_h)).json()["complaints"]
    pending = next((c for c in complaints if c["id"] == complaint_id), None)
    assert pending is not None, "Admin must see the complaint"
    assert pending["status"] == "PENDING"

    # Step 4 & 5: Admin assigns driver → complaint becomes IN_PROGRESS
    assign = await client.post(
        "/api/admin/assign_task",
        json={"complaint_id": complaint_id, "driver_id": driver_id,
              "waste_type": "Mixed", "address": "Demo Street, Demo Zone"},
        headers=admin_h
    )
    assert assign.status_code == 200
    task_id = assign.json()["task_id"]

    complaints_after = (await client.get("/api/admin/complaints", headers=admin_h)).json()["complaints"]
    after_assign = next(c for c in complaints_after if c["id"] == complaint_id)
    assert after_assign["status"] == "IN_PROGRESS"

    # Step 6: Driver sees task
    tasks = (await client.get("/api/driver/assigned_tasks", headers=driver_h)).json()["tasks"]
    my_task = next((t for t in tasks if t["complaint_id"] == complaint_id), None)
    assert my_task is not None, "Driver must see the assigned task"
    assert my_task["status"] == "ASSIGNED"

    # Step 7: Driver completes pickup
    complete = await client.post(
        "/api/driver/complete_pickup",
        data={"complaint_id": str(complaint_id)},
        headers=driver_h
    )
    assert complete.status_code == 200, f"Complete pickup failed: {complete.text}"

    # Step 8: Verify final state
    final_complaints = (await client.get("/api/admin/complaints", headers=admin_h)).json()["complaints"]
    final_complaint = next(c for c in final_complaints if c["id"] == complaint_id)
    assert final_complaint["status"] == "RESOLVED", (
        f"Complaint should be RESOLVED, got {final_complaint['status']}"
    )

    final_tasks = (await client.get("/api/driver/assigned_tasks", headers=driver_h)).json()["tasks"]
    final_task = next((t for t in final_tasks if t["complaint_id"] == complaint_id), None)
    assert final_task["status"] == "COMPLETED", (
        f"Task should be COMPLETED, got {final_task['status']}"
    )

    # Citizen can also see their complaint as RESOLVED
    citizen_reports = (await client.get("/api/citizen/my_reports", headers=citizen_h)).json()["reports"]
    citizen_complaint = next((r for r in citizen_reports if r["id"] == complaint_id), None)
    assert citizen_complaint is not None
    assert citizen_complaint["status"] == "RESOLVED"
