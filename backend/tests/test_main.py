import pytest
import os
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from main import app, get_db, Base, User, Complaint, DriverTask, DriverLocation
from auth import get_password_hash

# Set environment variables for testing
os.environ["SECRET_KEY"] = "testsecretkeytestsecretkeytestsecretkey"
os.environ["ENVIRONMENT"] = "testing"

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_scos.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

def test_read_root_redirects_to_app():
    """Verify that root URL redirects to index.html app preview page."""
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/app/Login%20Screen/index.html"

def test_cleanliness_score_empty_db():
    """Verify cleanliness score handles empty db correctly returning 100."""
    response = client.get("/api/citizen/cleanliness_score")
    assert response.status_code == 200
    data = response.json()
    assert "score" in data
    assert data["score"] == 100
    assert "label" in data
    assert data["label"] == "Perfect"

def test_cors_headers():
    """Verify whitelisted origins return correct CORS headers."""
    response = client.options(
        "/api/auth/login",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert response.headers.get("access-control-allow-credentials") == "true"

def test_invalid_login_credentials():
    """Verify that logging in with incorrect credentials returns 401."""
    response = client.post(
        "/api/auth/login",
        data={"username": "nonexistent@city.com", "password": "wrongpassword"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"

def test_registration_forces_citizen():
    """Verify registration endpoint forces CITIZEN role, ignoring any input."""
    response = client.post(
        "/api/auth/register",
        data={"email": "newcitizen@city.com", "password": "password", "name": "New Citizen"}
    )
    assert response.status_code == 200
    
    db = TestingSessionLocal()
    user = db.query(User).filter(User.email == "newcitizen@city.com").first()
    assert user is not None
    assert user.role == "CITIZEN"
    db.close()

def test_admin_endpoints_protection():
    """Verify admin endpoints are protected against anonymous and citizen users."""
    response = client.get("/api/admin/dashboard_stats")
    assert response.status_code == 401
    
    db = TestingSessionLocal()
    hashed_pwd = get_password_hash("password")
    citizen = User(name="Citizen John", email="citizen@city.com", role="CITIZEN", password_hash=hashed_pwd)
    db.add(citizen)
    db.commit()
    db.close()
    
    login_resp = client.post(
        "/api/auth/login",
        data={"username": "citizen@city.com", "password": "password"}
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/api/admin/dashboard_stats", headers=headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "Admin authorization required"

def test_admin_create_user_success():
    """Verify that an admin can create citizens, drivers, and admins."""
    db = TestingSessionLocal()
    hashed_pwd = get_password_hash("password")
    admin = User(name="Admin Alice", email="admin@city.com", role="ADMIN", password_hash=hashed_pwd)
    db.add(admin)
    db.commit()
    db.close()
    
    login_resp = client.post(
        "/api/auth/login",
        data={"username": "admin@city.com", "password": "password"}
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    response = client.post(
        "/api/admin/create_user",
        data={"email": "newdriver@city.com", "password": "password", "role": "DRIVER", "name": "New Driver"},
        headers=headers
    )
    assert response.status_code == 200
    assert "DRIVER created successfully" in response.json()["message"]
    
    db = TestingSessionLocal()
    user = db.query(User).filter(User.email == "newdriver@city.com").first()
    assert user is not None
    assert user.role == "DRIVER"
    db.close()

def test_driver_complete_pickup_synchronization(tmp_path):
    """Verify that completing a pickup successfully updates Complaint status and DriverTask status."""
    db = TestingSessionLocal()
    hashed_pwd = get_password_hash("password")
    driver = User(id=10, name="Driver Dave", email="driver@city.com", role="DRIVER", password_hash=hashed_pwd)
    complaint = Complaint(id=5, citizen_id=1, zone="Zone 1", area="Market", waste_type="Plastic", severity_level="High", status="PENDING", lat=12.9800, lng=77.6000)
    loc = DriverLocation(driver_id=10, lat=12.9800, lng=77.6000)
    task = DriverTask(driver_id=10, complaint_id=5, priority="HIGH", waste_type="Plastic", address="Market", status="ASSIGNED")
    db.add_all([driver, complaint, loc, task])
    db.commit()
    db.close()
    
    login_resp = client.post(
        "/api/auth/login",
        data={"username": "driver@city.com", "password": "password"}
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    proof_file = tmp_path / "proof.jpg"
    proof_file.write_bytes(b"dummy image bytes that are greater than 5KB to bypass mock fraud check. This text is long enough to make it > 5KB. Let's make sure it is indeed larger than 5120 bytes by adding more characters here..." * 50)
    
    with open(proof_file, "rb") as f:
        response = client.post(
            "/api/driver/complete_pickup",
            data={"complaint_id": 5},
            files={"proof_photo": ("proof.jpg", f, "image/jpeg")},
            headers=headers
        )
    
    assert response.status_code == 200
    assert response.json()["status"] == "SUCCESS"
    
    db = TestingSessionLocal()
    updated_complaint = db.query(Complaint).filter(Complaint.id == 5).first()
    assert updated_complaint.status == "RESOLVED"
    
    updated_task = db.query(DriverTask).filter(DriverTask.complaint_id == 5).first()
    assert updated_task.status == "COMPLETED"
    assert updated_task.completed_at is not None
    db.close()
