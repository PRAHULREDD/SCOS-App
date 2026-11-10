"""
SCOS Driver Proof-Photo Upload & Retrieval Verification Suite
Verifies all 7 core requirements:
1. Valid image upload & persistence
2. Invalid file rejection (wrong extension / invalid magic bytes)
3. Oversized file rejection (> 5MB)
4. Correct complaint/task linkage
5. Retrieval after a new session with role & ownership checks
6. Failed image persistence rollback (no phantom proof saved)
7. Existing pickup status transitions without photo still work
"""
import io
import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
from unittest.mock import patch

from main import app
from app.db.database import get_db
from app.models.domain import Base, User, Complaint, DriverTask
from app.core.auth import get_password_hash

os.environ["SECRET_KEY"] = "testsecretkeytestsecretkeytestsecretkey"
os.environ["ENVIRONMENT"] = "testing"

SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///./test_proof_photo.db"
engine = create_async_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(class_=AsyncSession, autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)


async def override_get_db():
    async with TestingSessionLocal() as db:
        yield db


@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_db():
    has_previous_override = get_db in app.dependency_overrides
    previous_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        if has_previous_override:
            app.dependency_overrides[get_db] = previous_override
        else:
            app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# Valid image samples
VALID_JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00\xff\xd9"
VALID_PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"


async def setup_pickup_fixture():
    """Seed citizen, driver1, driver2, admin, complaint, and task."""
    async with TestingSessionLocal() as db:
        citizen = User(
            name="Citizen One",
            email="citizen_proof@test.com",
            password_hash=get_password_hash("password123"),
            role="CITIZEN",
            eco_points=100
        )
        driver1 = User(
            name="Driver One",
            email="driver1_proof@test.com",
            password_hash=get_password_hash("password123"),
            role="DRIVER",
            eco_points=0
        )
        driver2 = User(
            name="Driver Two",
            email="driver2_proof@test.com",
            password_hash=get_password_hash("password123"),
            role="DRIVER",
            eco_points=0
        )
        admin = User(
            name="Admin One",
            email="admin_proof@test.com",
            password_hash=get_password_hash("password123"),
            role="ADMIN",
            eco_points=0
        )
        db.add_all([citizen, driver1, driver2, admin])
        await db.commit()
        await db.refresh(citizen)
        await db.refresh(driver1)
        await db.refresh(driver2)
        await db.refresh(admin)

        complaint = Complaint(
            citizen_id=citizen.id,
            zone="North",
            area="Hebbal",
            waste_type="PLASTIC",
            severity_level="HIGH",
            status="IN_PROGRESS",
            description="Test complaint for proof photo"
        )
        db.add(complaint)
        await db.commit()
        await db.refresh(complaint)

        task = DriverTask(
            driver_id=driver1.id,
            complaint_id=complaint.id,
            waste_type="PLASTIC",
            address="Hebbal Ring Road",
            status="ASSIGNED"
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)

        return {
            "citizen_id": citizen.id,
            "driver1_id": driver1.id,
            "driver2_id": driver2.id,
            "admin_id": admin.id,
            "complaint_id": complaint.id,
            "task_id": task.id
        }


async def login_user(client: AsyncClient, email: str) -> str:
    res = await client.post("/api/auth/login", data={"username": email, "password": "password123"})
    assert res.status_code == 200
    return res.json()["access_token"]


@pytest.mark.asyncio
async def test_1_valid_proof_photo_upload_and_persistence(client: AsyncClient):
    """1. Valid image upload: accepted, persisted, links task and complaint, sets status."""
    fixture = await setup_pickup_fixture()
    driver_token = await login_user(client, "driver1_proof@test.com")

    files = {
        "proof_photo": ("pickup_proof.jpg", io.BytesIO(VALID_JPEG_BYTES), "image/jpeg")
    }
    data = {"complaint_id": fixture["complaint_id"]}

    response = await client.post(
        "/api/driver/complete_pickup",
        data=data,
        files=files,
        headers={"Authorization": f"Bearer {driver_token}"}
    )

    assert response.status_code == 200, response.text
    resp_data = response.json()
    assert resp_data["message"] == "Pickup marked as complete"
    assert "proof_photo_url" in resp_data
    expected_url = f"/api/driver/proof/{fixture['task_id']}"
    assert resp_data["proof_photo_url"] == expected_url

    # Check database state
    async with TestingSessionLocal() as db:
        task = await db.get(DriverTask, fixture["task_id"])
        complaint = await db.get(Complaint, fixture["complaint_id"])

        assert task.status == "COMPLETED"
        assert task.proof_photo_url == expected_url
        assert complaint.status == "RESOLVED"
        assert complaint.proof_photo_url == expected_url


@pytest.mark.asyncio
async def test_2_invalid_file_rejection(client: AsyncClient):
    """2. Invalid file rejection: non-image text file or invalid magic bytes rejected with 400."""
    fixture = await setup_pickup_fixture()
    driver_token = await login_user(client, "driver1_proof@test.com")

    # Case A: disallowed extension
    files = {
        "proof_photo": ("malicious.exe", io.BytesIO(b"MZ\x90\x00program"), "application/x-msdownload")
    }
    response = await client.post(
        "/api/driver/complete_pickup",
        data={"complaint_id": fixture["complaint_id"]},
        files=files,
        headers={"Authorization": f"Bearer {driver_token}"}
    )
    assert response.status_code == 400
    assert "Unsupported file extension" in response.json()["detail"]

    # Case B: image extension but corrupted/invalid magic bytes
    files_fake = {
        "proof_photo": ("fake.jpg", io.BytesIO(b"Hello world this is not a JPEG"), "image/jpeg")
    }
    response2 = await client.post(
        "/api/driver/complete_pickup",
        data={"complaint_id": fixture["complaint_id"]},
        files=files_fake,
        headers={"Authorization": f"Bearer {driver_token}"}
    )
    assert response2.status_code == 400
    assert "Invalid image file format" in response2.json()["detail"]

    # Verify task was NOT completed
    async with TestingSessionLocal() as db:
        task = await db.get(DriverTask, fixture["task_id"])
        assert task.status == "ASSIGNED"


@pytest.mark.asyncio
async def test_3_oversized_file_rejection(client: AsyncClient):
    """3. Oversized file rejection: > 5MB file rejected with 413."""
    fixture = await setup_pickup_fixture()
    driver_token = await login_user(client, "driver1_proof@test.com")

    oversized_bytes = b"\xff\xd8\xff" + (b"A" * (5 * 1024 * 1024 + 10))
    files = {
        "proof_photo": ("huge.jpg", io.BytesIO(oversized_bytes), "image/jpeg")
    }

    response = await client.post(
        "/api/driver/complete_pickup",
        data={"complaint_id": fixture["complaint_id"]},
        files=files,
        headers={"Authorization": f"Bearer {driver_token}"}
    )
    assert response.status_code == 413
    assert "File size exceeds maximum allowed limit" in response.json()["detail"]

    # Verify task remains ASSIGNED
    async with TestingSessionLocal() as db:
        task = await db.get(DriverTask, fixture["task_id"])
        assert task.status == "ASSIGNED"


@pytest.mark.asyncio
async def test_4_correct_complaint_task_linkage(client: AsyncClient):
    """4. Correct complaint/task linkage: durable reference linked to specific task, not just driver."""
    fixture = await setup_pickup_fixture()
    driver_token = await login_user(client, "driver1_proof@test.com")

    files = {
        "proof_photo": ("proof.png", io.BytesIO(VALID_PNG_BYTES), "image/png")
    }
    res = await client.post(
        "/api/driver/complete_pickup",
        data={"complaint_id": fixture["complaint_id"]},
        files=files,
        headers={"Authorization": f"Bearer {driver_token}"}
    )
    assert res.status_code == 200

    async with TestingSessionLocal() as db:
        task = await db.get(DriverTask, fixture["task_id"])
        complaint = await db.get(Complaint, fixture["complaint_id"])

        assert task.complaint_id == fixture["complaint_id"]
        assert task.proof_photo_url == f"/api/driver/proof/{fixture['task_id']}"
        assert complaint.proof_photo_url == f"/api/driver/proof/{fixture['task_id']}"


@pytest.mark.asyncio
async def test_5_retrieval_and_role_ownership_checks(client: AsyncClient):
    """5. Retrieval after new session: Driver, Admin, Citizen can retrieve; other drivers blocked."""
    fixture = await setup_pickup_fixture()
    driver1_token = await login_user(client, "driver1_proof@test.com")

    # Upload proof photo
    files = {"proof_photo": ("valid.jpg", io.BytesIO(VALID_JPEG_BYTES), "image/jpeg")}
    res = await client.post(
        "/api/driver/complete_pickup",
        data={"complaint_id": fixture["complaint_id"]},
        files=files,
        headers={"Authorization": f"Bearer {driver1_token}"}
    )
    assert res.status_code == 200
    proof_url = res.json()["proof_photo_url"]

    # A. Driver 1 retrieves proof
    res_driver = await client.get(proof_url, headers={"Authorization": f"Bearer {driver1_token}"})
    assert res_driver.status_code == 200
    assert res_driver.headers["content-type"] == "image/jpeg"
    assert res_driver.content == VALID_JPEG_BYTES

    # B. Citizen who filed the complaint retrieves proof in fresh session
    citizen_token = await login_user(client, "citizen_proof@test.com")
    res_citizen = await client.get(proof_url, headers={"Authorization": f"Bearer {citizen_token}"})
    assert res_citizen.status_code == 200
    assert res_citizen.content == VALID_JPEG_BYTES

    # C. Admin retrieves proof in fresh session
    admin_token = await login_user(client, "admin_proof@test.com")
    res_admin = await client.get(proof_url, headers={"Authorization": f"Bearer {admin_token}"})
    assert res_admin.status_code == 200
    assert res_admin.content == VALID_JPEG_BYTES

    # D. Unassigned Driver 2 attempts to retrieve proof -> 403 Forbidden
    driver2_token = await login_user(client, "driver2_proof@test.com")
    res_unauthorized = await client.get(proof_url, headers={"Authorization": f"Bearer {driver2_token}"})
    assert res_unauthorized.status_code == 403
    assert "Forbidden" in res_unauthorized.json()["detail"]


@pytest.mark.asyncio
async def test_6_failed_image_persistence_does_not_silently_report_success(client: AsyncClient):
    """6. Failed image persistence rolls back status and raises 500 without reporting success."""
    fixture = await setup_pickup_fixture()
    driver_token = await login_user(client, "driver1_proof@test.com")

    files = {"proof_photo": ("valid.jpg", io.BytesIO(VALID_JPEG_BYTES), "image/jpeg")}

    # Mock disk failure during file write
    with patch("builtins.open", side_effect=OSError("Disk write I/O error")):
        response = await client.post(
            "/api/driver/complete_pickup",
            data={"complaint_id": fixture["complaint_id"]},
            files=files,
            headers={"Authorization": f"Bearer {driver_token}"}
        )
        assert response.status_code == 500
        assert "Failed to persist proof photo" in response.json()["detail"]

    # Verify database state was NOT modified
    async with TestingSessionLocal() as db:
        task = await db.get(DriverTask, fixture["task_id"])
        complaint = await db.get(Complaint, fixture["complaint_id"])

        assert task.status == "ASSIGNED"
        assert task.proof_photo_url is None
        assert complaint.status == "IN_PROGRESS"
        assert complaint.proof_photo_url is None


@pytest.mark.asyncio
async def test_7_existing_pickup_status_transitions_without_photo_work(client: AsyncClient):
    """7. Existing pickup status transitions: completing pickup without photo still succeeds."""
    fixture = await setup_pickup_fixture()
    driver_token = await login_user(client, "driver1_proof@test.com")

    # Complete pickup with NO proof_photo attached
    response = await client.post(
        "/api/driver/complete_pickup",
        data={"complaint_id": fixture["complaint_id"]},
        headers={"Authorization": f"Bearer {driver_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Pickup marked as complete"
    assert data["task_id"] == fixture["task_id"]
    assert "proof_photo_url" not in data

    async with TestingSessionLocal() as db:
        task = await db.get(DriverTask, fixture["task_id"])
        complaint = await db.get(Complaint, fixture["complaint_id"])

        assert task.status == "COMPLETED"
        assert task.proof_photo_url is None
        assert complaint.status == "RESOLVED"
        assert complaint.proof_photo_url is None
