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
import asyncio
import io
import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
from unittest.mock import patch
from pathlib import Path

from main import app
from app.db.database import get_db
from app.models.domain import Base, User, Complaint, DriverTask
from app.core.auth import get_password_hash
from app.services.storage_service import (
    get_storage_service,
    reset_storage_service,
    LocalStorageService,
    StorageError,
)

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


@pytest_asyncio.fixture(scope="function", autouse=True)
async def isolate_storage(tmp_path: Path):
    """
    Test isolation fixture: Redirects all proof-photo storage operations to an
    isolated tmp_path directory. Ensures tests NEVER write to backend/uploads/proof_photos/.
    """
    test_storage_dir = tmp_path / "test_proof_photos"
    test_storage_dir.mkdir(parents=True, exist_ok=True)
    test_service = LocalStorageService(storage_root=test_storage_dir)

    has_previous_override = get_storage_service in app.dependency_overrides
    previous_override = app.dependency_overrides.get(get_storage_service)
    app.dependency_overrides[get_storage_service] = lambda: test_service
    reset_storage_service()

    try:
        yield test_service
    finally:
        if has_previous_override:
            app.dependency_overrides[get_storage_service] = previous_override
        else:
            app.dependency_overrides.pop(get_storage_service, None)
        reset_storage_service()


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

    # Mock storage failure during file write
    with patch.object(LocalStorageService, "save_file", side_effect=StorageError("Disk write I/O error")):
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


@pytest.mark.asyncio
async def test_8_citizen_my_reports_includes_proof_photo_url_when_available(client: AsyncClient):
    """8. Citizen my_reports returns proof_photo_url when proof photo exists, and None otherwise."""
    fixture = await setup_pickup_fixture()
    driver_token = await login_user(client, "driver1_proof@test.com")
    citizen_token = await login_user(client, "citizen_proof@test.com")

    # Before completion: proof_photo_url is None
    res_before = await client.get("/api/citizen/my_reports", headers={"Authorization": f"Bearer {citizen_token}"})
    assert res_before.status_code == 200
    reports_before = res_before.json()["reports"]
    c_before = next(r for r in reports_before if r["id"] == fixture["complaint_id"])
    assert c_before["proof_photo_url"] is None

    # Complete pickup with valid photo
    files = {"proof_photo": ("valid.jpg", io.BytesIO(VALID_JPEG_BYTES), "image/jpeg")}
    res_complete = await client.post(
        "/api/driver/complete_pickup",
        data={"complaint_id": fixture["complaint_id"]},
        files=files,
        headers={"Authorization": f"Bearer {driver_token}"}
    )
    assert res_complete.status_code == 200

    # After completion: proof_photo_url is present and matches driver task proof route
    res_after = await client.get("/api/citizen/my_reports", headers={"Authorization": f"Bearer {citizen_token}"})
    assert res_after.status_code == 200
    reports_after = res_after.json()["reports"]
    c_after = next(r for r in reports_after if r["id"] == fixture["complaint_id"])
    assert c_after["status"] == "RESOLVED"
    assert c_after["proof_photo_url"] == f"/api/driver/proof/{fixture['task_id']}"


@pytest.mark.asyncio
async def test_9_admin_complaints_includes_proof_photo_url_when_available(client: AsyncClient):
    """9. Admin complaints list returns proof_photo_url when available."""
    fixture = await setup_pickup_fixture()
    driver_token = await login_user(client, "driver1_proof@test.com")
    admin_token = await login_user(client, "admin_proof@test.com")

    # Complete pickup with valid photo
    files = {"proof_photo": ("valid.png", io.BytesIO(VALID_PNG_BYTES), "image/png")}
    res_complete = await client.post(
        "/api/driver/complete_pickup",
        data={"complaint_id": fixture["complaint_id"]},
        files=files,
        headers={"Authorization": f"Bearer {driver_token}"}
    )
    assert res_complete.status_code == 200

    # Admin lists complaints
    res_admin = await client.get("/api/admin/complaints", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_admin.status_code == 200
    complaints = res_admin.json()["complaints"]
    target = next(c for c in complaints if c["id"] == fixture["complaint_id"])
    assert target["status"] == "RESOLVED"
    assert target["proof_photo_url"] == f"/api/driver/proof/{fixture['task_id']}"


@pytest.mark.asyncio
async def test_10_citizen_cannot_retrieve_other_citizens_proof(client: AsyncClient):
    """10. Role isolation: A citizen cannot retrieve proof photos for complaints filed by another citizen."""
    fixture = await setup_pickup_fixture()
    driver_token = await login_user(client, "driver1_proof@test.com")

    # Complete pickup with valid photo for Citizen 1's complaint
    files = {"proof_photo": ("valid.jpg", io.BytesIO(VALID_JPEG_BYTES), "image/jpeg")}
    res_complete = await client.post(
        "/api/driver/complete_pickup",
        data={"complaint_id": fixture["complaint_id"]},
        files=files,
        headers={"Authorization": f"Bearer {driver_token}"}
    )
    assert res_complete.status_code == 200
    proof_url = res_complete.json()["proof_photo_url"]

    # Create Citizen 2 in database
    async with TestingSessionLocal() as db:
        citizen2 = User(
            name="Citizen Two",
            email="citizen2_proof@test.com",
            password_hash=get_password_hash("password123"),
            role="CITIZEN",
            eco_points=50
        )
        db.add(citizen2)
        await db.commit()

    # Citizen 2 attempts to retrieve Citizen 1's proof -> 403 Forbidden
    citizen2_token = await login_user(client, "citizen2_proof@test.com")
    res_unauth = await client.get(proof_url, headers={"Authorization": f"Bearer {citizen2_token}"})
    assert res_unauth.status_code == 403
    assert "Forbidden: You did not submit the complaint for this pickup" in res_unauth.json()["detail"]


@pytest.mark.asyncio
async def test_11_waste_heatmap_includes_proof_metadata(client: AsyncClient):
    """11. Admin waste_heatmap returns id and proof_photo_url metadata for mapped points."""
    fixture = await setup_pickup_fixture()
    driver_token = await login_user(client, "driver1_proof@test.com")
    admin_token = await login_user(client, "admin_proof@test.com")

    # Set coordinates on fixture complaint
    async with TestingSessionLocal() as db:
        c = await db.get(Complaint, fixture["complaint_id"])
        c.lat = 12.9716
        c.lng = 77.5946
        db.add(c)
        await db.commit()

    # Complete pickup with photo
    files = {"proof_photo": ("valid.jpg", io.BytesIO(VALID_JPEG_BYTES), "image/jpeg")}
    await client.post(
        "/api/driver/complete_pickup",
        data={"complaint_id": fixture["complaint_id"]},
        files=files,
        headers={"Authorization": f"Bearer {driver_token}"}
    )

    res = await client.get("/api/admin/waste_heatmap", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    points = res.json()["heatmap_points"]
    target = next((p for p in points if p.get("id") == fixture["complaint_id"]), None)
    assert target is not None
    assert target["status"] == "RESOLVED"
    assert target["proof_photo_url"] == f"/api/driver/proof/{fixture['task_id']}"


@pytest.mark.asyncio
async def test_12_db_commit_failure_cleans_up_newly_created_storage_object(client: AsyncClient, isolate_storage: LocalStorageService):
    """12. If database commit fails, the transaction rolls back and only the newly created storage object is deleted."""
    fixture = await setup_pickup_fixture()
    driver_token = await login_user(client, "driver1_proof@test.com")

    # Seed a pre-existing unrelated proof to ensure it survives
    pre_existing_key = "proofs/tasks/task_999.jpg"
    await isolate_storage.save_file(pre_existing_key, b"pre-existing", "image/jpeg")
    assert await isolate_storage.exists(pre_existing_key) is True

    files = {"proof_photo": ("valid.jpg", io.BytesIO(VALID_JPEG_BYTES), "image/jpeg")}

    with patch.object(AsyncSession, "commit", side_effect=Exception("Database commit disk error")):
        response = await client.post(
            "/api/driver/complete_pickup",
            data={"complaint_id": fixture["complaint_id"]},
            files=files,
            headers={"Authorization": f"Bearer {driver_token}"}
        )
        assert response.status_code == 500
        assert "Database commit failed during pickup completion" in response.json()["detail"]

    # Newly created object was cleaned up
    expected_new_key = f"proofs/tasks/task_{fixture['task_id']}.jpg"
    assert await isolate_storage.exists(expected_new_key) is False

    # Pre-existing object survived untouched
    assert await isolate_storage.exists(pre_existing_key) is True


@pytest.mark.asyncio
async def test_13_repeated_pickup_completion_rejected_with_409(client: AsyncClient, isolate_storage: LocalStorageService):
    """13. Attempting to complete an already completed pickup is rejected with 409 and does not destroy existing proof."""
    fixture = await setup_pickup_fixture()
    driver_token = await login_user(client, "driver1_proof@test.com")

    # Complete pickup successfully
    files1 = {"proof_photo": ("valid.jpg", io.BytesIO(VALID_JPEG_BYTES), "image/jpeg")}
    res1 = await client.post(
        "/api/driver/complete_pickup",
        data={"complaint_id": fixture["complaint_id"]},
        files=files1,
        headers={"Authorization": f"Bearer {driver_token}"}
    )
    assert res1.status_code == 200

    storage_key = f"proofs/tasks/task_{fixture['task_id']}.jpg"
    assert await isolate_storage.exists(storage_key) is True
    original_stored = await isolate_storage.get_file(storage_key)
    assert original_stored.content == VALID_JPEG_BYTES

    # Attempt to complete pickup again with different bytes
    files2 = {"proof_photo": ("new.jpg", io.BytesIO(b"\xff\xd8\xff\xe0\x00\x10JFIFdifferent"), "image/jpeg")}
    res2 = await client.post(
        "/api/driver/complete_pickup",
        data={"complaint_id": fixture["complaint_id"]},
        files=files2,
        headers={"Authorization": f"Bearer {driver_token}"}
    )
    assert res2.status_code == 409
    assert "Pickup already completed" in res2.json()["detail"]

    # Original proof remains untouched
    persisted_stored = await isolate_storage.get_file(storage_key)
    assert persisted_stored.content == VALID_JPEG_BYTES


@pytest.mark.asyncio
async def test_14_unassigned_driver_completion_rejected(client: AsyncClient):
    """14. An unassigned driver attempting to complete another driver's task is rejected with 404."""
    fixture = await setup_pickup_fixture()
    driver2_token = await login_user(client, "driver2_proof@test.com")

    files = {"proof_photo": ("valid.jpg", io.BytesIO(VALID_JPEG_BYTES), "image/jpeg")}
    res = await client.post(
        "/api/driver/complete_pickup",
        data={"complaint_id": fixture["complaint_id"]},
        files=files,
        headers={"Authorization": f"Bearer {driver2_token}"}
    )
    assert res.status_code == 404
    assert "No task found for this complaint assigned to you" in res.json()["detail"]


@pytest.mark.asyncio
async def test_15_retrieval_route_aliases_and_missing_object(client: AsyncClient, isolate_storage: LocalStorageService):
    """15. Verifies both /proof/{id} and /proof_photo/{id} aliases work identically, and missing objects return 404."""
    fixture = await setup_pickup_fixture()
    driver_token = await login_user(client, "driver1_proof@test.com")

    files = {"proof_photo": ("valid.jpg", io.BytesIO(VALID_JPEG_BYTES), "image/jpeg")}
    res = await client.post(
        "/api/driver/complete_pickup",
        data={"complaint_id": fixture["complaint_id"]},
        files=files,
        headers={"Authorization": f"Bearer {driver_token}"}
    )
    assert res.status_code == 200

    # Route 1: /api/driver/proof/{task_id}
    res_r1 = await client.get(f"/api/driver/proof/{fixture['task_id']}", headers={"Authorization": f"Bearer {driver_token}"})
    assert res_r1.status_code == 200
    assert res_r1.content == VALID_JPEG_BYTES

    # Route 2: /api/driver/proof_photo/{task_id}
    res_r2 = await client.get(f"/api/driver/proof_photo/{fixture['task_id']}", headers={"Authorization": f"Bearer {driver_token}"})
    assert res_r2.status_code == 200
    assert res_r2.content == VALID_JPEG_BYTES

    # Delete storage file behind the scenes -> should return 404
    storage_key = f"proofs/tasks/task_{fixture['task_id']}.jpg"
    await isolate_storage.delete_file(storage_key)

    res_missing = await client.get(f"/api/driver/proof/{fixture['task_id']}", headers={"Authorization": f"Bearer {driver_token}"})
    assert res_missing.status_code == 404
    assert "Proof photo file not found" in res_missing.json()["detail"]


@pytest.mark.asyncio
async def test_16_storage_provider_failure_returns_500(client: AsyncClient, isolate_storage: LocalStorageService):
    """16. Storage provider exceptions during retrieval return HTTP 500 Storage provider error."""
    fixture = await setup_pickup_fixture()
    driver_token = await login_user(client, "driver1_proof@test.com")

    files = {"proof_photo": ("valid.jpg", io.BytesIO(VALID_JPEG_BYTES), "image/jpeg")}
    await client.post(
        "/api/driver/complete_pickup",
        data={"complaint_id": fixture["complaint_id"]},
        files=files,
        headers={"Authorization": f"Bearer {driver_token}"}
    )

    with patch.object(isolate_storage, "exists", side_effect=StorageError("Cloudflare R2 timeout")):
        res = await client.get(f"/api/driver/proof/{fixture['task_id']}", headers={"Authorization": f"Bearer {driver_token}"})
        assert res.status_code == 500
        assert "Storage provider error" in res.json()["detail"]


@pytest.mark.asyncio
async def test_17_legacy_compatibility_single_unambiguous_file(client: AsyncClient, isolate_storage: LocalStorageService):
    """17. Single unambiguous legacy file on disk is successfully served when DB has proof_url."""
    fixture = await setup_pickup_fixture()
    driver_token = await login_user(client, "driver1_proof@test.com")

    # Manually configure DB record to have proof_url
    async with TestingSessionLocal() as db:
        task = await db.get(DriverTask, fixture["task_id"])
        task.status = "COMPLETED"
        task.proof_photo_url = f"/api/driver/proof/{fixture['task_id']}"
        db.add(task)
        await db.commit()

    # Create exactly ONE legacy file matching task_{task_id}_*
    legacy_file = isolate_storage.storage_root / f"task_{fixture['task_id']}_complaint_{fixture['complaint_id']}_random123.jpg"
    legacy_file.write_bytes(VALID_JPEG_BYTES)

    res = await client.get(f"/api/driver/proof/{fixture['task_id']}", headers={"Authorization": f"Bearer {driver_token}"})
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/jpeg"
    assert res.content == VALID_JPEG_BYTES


@pytest.mark.asyncio
async def test_18_legacy_compatibility_multiple_ambiguous_files_rejected_with_409(client: AsyncClient, isolate_storage: LocalStorageService):
    """18. Multiple candidate legacy files are rejected with 409 Conflict instead of arbitrarily picking one."""
    fixture = await setup_pickup_fixture()
    driver_token = await login_user(client, "driver1_proof@test.com")

    async with TestingSessionLocal() as db:
        task = await db.get(DriverTask, fixture["task_id"])
        task.status = "COMPLETED"
        task.proof_photo_url = f"/api/driver/proof/{fixture['task_id']}"
        db.add(task)
        await db.commit()

    # Create TWO legacy files matching task_{task_id}_*
    file1 = isolate_storage.storage_root / f"task_{fixture['task_id']}_first.jpg"
    file2 = isolate_storage.storage_root / f"task_{fixture['task_id']}_second.jpg"
    file1.write_bytes(VALID_JPEG_BYTES)
    file2.write_bytes(VALID_JPEG_BYTES)

    res = await client.get(f"/api/driver/proof/{fixture['task_id']}", headers={"Authorization": f"Bearer {driver_token}"})
    assert res.status_code == 409
    assert "Ambiguous legacy proof photos found" in res.json()["detail"]


@pytest.mark.asyncio
async def test_19_legacy_compatibility_no_db_proof_url_never_serves_legacy_file(client: AsyncClient, isolate_storage: LocalStorageService):
    """19. If DB task.proof_photo_url is None, legacy files are never served even if matching files exist on disk."""
    fixture = await setup_pickup_fixture()
    driver_token = await login_user(client, "driver1_proof@test.com")

    # DB task has proof_photo_url = None
    legacy_file = isolate_storage.storage_root / f"task_{fixture['task_id']}_orphan.jpg"
    legacy_file.write_bytes(VALID_JPEG_BYTES)

    res = await client.get(f"/api/driver/proof/{fixture['task_id']}", headers={"Authorization": f"Bearer {driver_token}"})
    assert res.status_code == 404
    assert "No proof photo uploaded for this task" in res.json()["detail"]


@pytest.mark.asyncio
async def test_20_test_isolation_verifies_app_uploads_untouched():
    """20. Confirms backend/uploads/proof_photos/ contains exactly 84 files and zero test pollution."""
    if os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true":
        pytest.skip("Local seed proof_photos directory is not tracked in Git and is absent in CI.")
    app_uploads = Path(__file__).resolve().parent.parent / "uploads" / "proof_photos"
    files = list(app_uploads.glob("*"))
    assert len(files) == 84


@pytest.mark.asyncio
async def test_21_concurrent_pickup_completion_only_one_succeeds(client: AsyncClient, isolate_storage: LocalStorageService):
    """
    21. Verifies that when two completion requests for the same task run concurrently:
    1. Exactly one request succeeds with 200 OK.
    2. The losing request is rejected with 409 Conflict.
    3. The losing request cannot overwrite the winning proof.
    4. The losing request's rollback cannot delete the winning proof.
    5. The winning proof remains intact and retrievable in storage and via API.
    """
    fixture = await setup_pickup_fixture()
    driver_token = await login_user(client, "driver1_proof@test.com")

    file1_bytes = VALID_JPEG_BYTES
    file2_bytes = VALID_PNG_BYTES

    async def send_completion(filename: str, content: bytes, mime: str):
        files = {"proof_photo": (filename, io.BytesIO(content), mime)}
        return await client.post(
            "/api/driver/complete_pickup",
            data={"complaint_id": fixture["complaint_id"]},
            files=files,
            headers={"Authorization": f"Bearer {driver_token}"}
        )

    resp1, resp2 = await asyncio.gather(
        send_completion("proof1.jpg", file1_bytes, "image/jpeg"),
        send_completion("proof2.png", file2_bytes, "image/png"),
        return_exceptions=False
    )

    statuses = sorted([resp1.status_code, resp2.status_code])
    assert statuses == [200, 409], f"Expected exactly one 200 and one 409, got: {statuses}"

    winning_resp = resp1 if resp1.status_code == 200 else resp2
    losing_resp = resp2 if resp1.status_code == 200 else resp1

    assert "Pickup marked as complete" in winning_resp.json()["message"]
    assert "Pickup already completed" in losing_resp.json()["detail"]

    # Verify task state in database
    async with TestingSessionLocal() as db:
        task = await db.get(DriverTask, fixture["task_id"])
        complaint = await db.get(Complaint, fixture["complaint_id"])
        assert task.status == "COMPLETED"
        assert task.proof_photo_url == f"/api/driver/proof/{fixture['task_id']}"
        assert complaint.status == "RESOLVED"
        assert complaint.proof_photo_url == f"/api/driver/proof/{fixture['task_id']}"

    # Verify proof retrieval returns winning file
    retrieval_res = await client.get(
        f"/api/driver/proof/{fixture['task_id']}",
        headers={"Authorization": f"Bearer {driver_token}"}
    )
    assert retrieval_res.status_code == 200
    expected_bytes = file1_bytes if resp1.status_code == 200 else file2_bytes
    assert retrieval_res.content == expected_bytes


@pytest.mark.asyncio
async def test_22_concurrent_completion_rollback_does_not_delete_winning_proof(client: AsyncClient, isolate_storage: LocalStorageService):
    """
    22. Verifies that when a concurrent attempt fails or is rejected, its rollback cleanup
    never deletes the winning request's persisted proof photo.
    """
    fixture = await setup_pickup_fixture()
    driver_token = await login_user(client, "driver1_proof@test.com")

    # Complete the task legitimately first
    files = {"proof_photo": ("valid.jpg", io.BytesIO(VALID_JPEG_BYTES), "image/jpeg")}
    res_legit = await client.post(
        "/api/driver/complete_pickup",
        data={"complaint_id": fixture["complaint_id"]},
        files=files,
        headers={"Authorization": f"Bearer {driver_token}"}
    )
    assert res_legit.status_code == 200

    storage_key = f"proofs/tasks/task_{fixture['task_id']}.jpg"
    assert await isolate_storage.exists(storage_key) is True

    # Now simulate a duplicate completion attempt
    files_dup = {"proof_photo": ("another.jpg", io.BytesIO(VALID_JPEG_BYTES), "image/jpeg")}
    res_dup = await client.post(
        "/api/driver/complete_pickup",
        data={"complaint_id": fixture["complaint_id"]},
        files=files_dup,
        headers={"Authorization": f"Bearer {driver_token}"}
    )
    assert res_dup.status_code == 409
    assert "Pickup already completed" in res_dup.json()["detail"]

    # Verify the legitimate proof was not deleted
    assert await isolate_storage.exists(storage_key) is True
    stored = await isolate_storage.get_file(storage_key)
    assert stored.content == VALID_JPEG_BYTES


@pytest.mark.asyncio
async def test_23_zero_byte_jpg_upload_rejected_with_400(client: AsyncClient, isolate_storage: LocalStorageService):
    """23. Zero-byte .jpg upload is rejected with HTTP 400 and does not complete pickup or write storage."""
    fixture = await setup_pickup_fixture()
    driver_token = await login_user(client, "driver1_proof@test.com")

    files = {"proof_photo": ("empty.jpg", io.BytesIO(b""), "image/jpeg")}
    res = await client.post(
        "/api/driver/complete_pickup",
        data={"complaint_id": fixture["complaint_id"]},
        files=files,
        headers={"Authorization": f"Bearer {driver_token}"}
    )
    assert res.status_code == 400
    assert "Empty file uploaded" in res.json()["detail"]

    # Verify task state in database remains unchanged
    async with TestingSessionLocal() as db:
        task = await db.get(DriverTask, fixture["task_id"])
        complaint = await db.get(Complaint, fixture["complaint_id"])
        assert task.status == "ASSIGNED"
        assert task.proof_photo_url is None
        assert complaint.status == "IN_PROGRESS"

    # Verify no storage file was created
    storage_key = f"proofs/tasks/task_{fixture['task_id']}.jpg"
    assert await isolate_storage.exists(storage_key) is False


@pytest.mark.asyncio
async def test_24_zero_byte_png_upload_rejected_with_400(client: AsyncClient, isolate_storage: LocalStorageService):
    """24. Zero-byte .png upload is rejected with HTTP 400."""
    fixture = await setup_pickup_fixture()
    driver_token = await login_user(client, "driver1_proof@test.com")

    files = {"proof_photo": ("empty.png", io.BytesIO(b""), "image/png")}
    res = await client.post(
        "/api/driver/complete_pickup",
        data={"complaint_id": fixture["complaint_id"]},
        files=files,
        headers={"Authorization": f"Bearer {driver_token}"}
    )
    assert res.status_code == 400
    assert "Empty file uploaded" in res.json()["detail"]
