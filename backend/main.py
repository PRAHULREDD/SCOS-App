import os
import httpx
import math
import time
import uuid
import logging
import structlog
import sentry_sdk
from prometheus_client import Gauge, Histogram
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import event
from fastapi import FastAPI, Depends, File, UploadFile, Form, HTTPException, status, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from datetime import datetime, timedelta

from auth import verify_password, get_password_hash, create_access_token, create_refresh_token, decode_access_token, decode_refresh_token

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./scos.db")
AI_ENGINE_URL = os.getenv("AI_ENGINE_URL", "http://localhost:8001") # Local fallback

def haversine_distance(lat1, lon1, lat2, lon2):
    # Radius of the Earth in km
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c * 1000 # returns distance in meters

# Initialize Sentry
SENTRY_DSN = os.getenv("SENTRY_DSN")
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
    )

# Configure structlog for JSON logging
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.dict_tracebacks,
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    cache_logger_on_first_use=True,
)
logger = structlog.get_logger()

# Prometheus Custom Metrics
websocket_connections_active = Gauge("websocket_connections_active", "Number of active websocket connections")
db_query_duration_seconds = Histogram("db_query_duration_seconds", "Duration of DB queries in seconds")

# SQLAlchemy setup
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

# Event listeners to time SQL queries
@event.listens_for(engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    context._query_start_time = time.perf_counter()

@event.listens_for(engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    if hasattr(context, "_query_start_time"):
        total_time = time.perf_counter() - context._query_start_time
        db_query_duration_seconds.observe(total_time)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

app = FastAPI(title="Smart Waste Collection - Backend API")

# Initialize Prometheus Instrumentator
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

# Structured request logger middleware
@app.middleware("http")
async def add_process_time_and_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)
    
    start_time = time.perf_counter()
    try:
        response = await call_next(request)
        process_time = time.perf_counter() - start_time
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_s=process_time,
            client_ip=request.client.host if request.client else None,
        )
        return response
    except Exception as exc:
        process_time = time.perf_counter() - start_time
        logger.error(
            "http_request_failed",
            method=request.method,
            path=request.url.path,
            error=str(exc),
            duration_s=process_time,
            client_ip=request.client.host if request.client else None,
        )
        raise exc

# Rate Limiter
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Serve Flutter Web App
app.mount("/app", StaticFiles(directory="static/app", html=True), name="app")

# Serve shared JavaScript assets
app.mount("/js", StaticFiles(directory="static/js"), name="js")


@app.get("/")
def read_root():
    return RedirectResponse(url="/app/Login%20Screen/index.html")

@app.get("/api/health")
def health_check():
    return {"status": "ok"}

# Enable CORS for the Admin Dashboard HTML frontend
CORS_ORIGINS_ENV = os.getenv("CORS_ORIGINS")
if CORS_ORIGINS_ENV:
    CORS_ORIGINS = [origin.strip() for origin in CORS_ORIGINS_ENV.split(",") if origin.strip()]
else:
    CORS_ORIGINS = [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:8081",
        "http://127.0.0.1:8081",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# ----------------- Real-time Connection Manager -----------------
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def disappearance(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        websocket_connections_active.set(len(self.active_connections))

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        websocket_connections_active.set(len(self.active_connections))

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

@app.websocket("/ws/fleet")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and receive any updates
            data = await websocket.receive_json()
            # In a real scenario, we'd process GPS updates from drivers here
            # and broadcast them to admins
            await manager.broadcast(data)
    except WebSocketDisconnect:
        await manager.disappearance(websocket)
    except Exception:
        await manager.disappearance(websocket)

# ----------------- DB Models -----------------
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    role = Column(String) # CITIZEN, DRIVER, ADMIN
    eco_points = Column(Integer, default=0)

class Complaint(Base):
    __tablename__ = "complaints"
    id = Column(Integer, primary_key=True, index=True)
    citizen_id = Column(Integer)
    zone = Column(String)
    area = Column(String)
    waste_type = Column(String)
    severity_level = Column(String)
    status = Column(String, default="PENDING")
    lat = Column(Float)
    lng = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

class DriverLocation(Base):
    __tablename__ = "driver_locations"
    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer)
    lat = Column(Float)
    lng = Column(Float)
    updated_at = Column(DateTime, default=datetime.utcnow)

class Reward(Base):
    __tablename__ = "rewards"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    provider = Column(String)
    category = Column(String)
    points_cost = Column(Integer)
    image_url = Column(String)
    is_active = Column(Integer, default=1)

class RewardRedemption(Base):
    __tablename__ = "reward_redemptions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    reward_id = Column(Integer)
    redeemed_at = Column(DateTime, default=datetime.utcnow)

class DriverTask(Base):
    __tablename__ = "driver_tasks"
    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer)
    complaint_id = Column(Integer)
    priority = Column(String, default="MEDIUM")
    waste_type = Column(String)
    address = Column(String)
    bin_fill_percent = Column(Integer, default=50)
    distance_km = Column(Float, default=0)
    status = Column(String, default="ASSIGNED")
    assigned_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

class DumpingIncident(Base):
    __tablename__ = "dumping_incidents"
    id = Column(Integer, primary_key=True, index=True)
    zone = Column(String)
    cluster_id = Column(String)
    description = Column(String)
    severity = Column(String, default="MEDIUM")
    predicted_culprit = Column(String)
    common_time = Column(String)
    confidence = Column(Float, default=0)
    lat = Column(Float)
    lng = Column(Float)
    status = Column(String, default="ACTIVE")
    detected_at = Column(DateTime, default=datetime.utcnow)
    dispatched_at = Column(DateTime, nullable=True)

class Contractor(Base):
    __tablename__ = "contractors"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    completion_rate = Column(Float, default=0)
    satisfaction_score = Column(Float, default=0)
    response_time_hours = Column(Float, default=0)
    active_drivers = Column(Integer, default=0)

# ----------------- DB Initialization -----------------
import time
def init_db():
    for i in range(10):
        try:
            Base.metadata.create_all(bind=engine)
            print("Database tables synchronized.")
            
            # Auto-seed initial data if empty
            db = SessionLocal()
            if db.query(Reward).count() == 0:
                rewards = [
                    Reward(title="Free Oat Latte", provider="The Green Bean", cost=450, points_cost=450, category="Local Shop"),
                    Reward(title="Botanic Garden Pass", provider="City Parks Dept", cost=800, points_cost=800, category="Public Service"),
                    Reward(title="15% Off Organic Box", provider="Farm-to-Door", cost=300, points_cost=300, category="Discount"),
                    Reward(title="Weekly Transit Pass", provider="Metro Transit", cost=1500, points_cost=1500, category="Transport")
                ]
                db.add_all(rewards)
            
            if db.query(Contractor).count() == 0:
                contractors = [
                    Contractor(name="GreenFleet Logistics", completion_rate=98.2, satisfaction_score=4.8, response_time_hours=2.4, active_drivers=12),
                    Contractor(name="CityWorks Sanitation", completion_rate=94.5, satisfaction_score=4.2, response_time_hours=4.1, active_drivers=8)
                ]
                db.add_all(contractors)
                
            if db.query(DumpingIncident).count() == 0:
                incidents = [
                    DumpingIncident(zone="Zone A", cluster_id="CL-409", description="Construction debris on sidewalk", severity="HIGH", predicted_culprit="Unlicensed Contractor", confidence=0.88, lat=12.9716, lng=77.5946),
                    DumpingIncident(zone="Zone C", cluster_id="CL-112", description="Household waste in alleyway", severity="MEDIUM", predicted_culprit="Local Residents", confidence=0.65, lat=12.9780, lng=77.5990)
                ]
                db.add_all(incidents)
                
            if db.query(Complaint).count() == 0:
                complaints = [
                    Complaint(citizen_id=1, lat=12.9716, lng=77.5946, zone="Zone A", area="Downtown", waste_type="General", severity_level="High", status="PENDING"),
                    Complaint(citizen_id=1, lat=12.9750, lng=77.5980, zone="Zone B", area="Northside", waste_type="Recyclable", severity_level="Medium", status="RESOLVED"),
                    Complaint(citizen_id=1, lat=12.9720, lng=77.5900, zone="Zone C", area="West End", waste_type="Hazardous", severity_level="High", status="PENDING")
                ]
                db.add_all(complaints)
                
            db.commit()
            db.close()
            
            break
        except Exception as e:
            print(f"Waiting for database... ({i+1}/10) Error: {e}")
            time.sleep(3)

init_db()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ----------------- Dependencies -----------------
async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    email = payload.get("sub")
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

def verify_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Admin authorization required"
        )
    return current_user

# ----------------- Validation Schemas -----------------
from pydantic import BaseModel, Field, field_validator, ValidationError

class UserRegister(BaseModel):
    email: str = Field(..., max_length=100)
    password: str = Field(..., min_length=6, max_length=100)
    name: str = Field(..., min_length=2, max_length=100)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        if "@" not in v:
            raise ValueError("Invalid email format")
        return v

class AdminCreateUser(BaseModel):
    email: str = Field(..., max_length=100)
    password: str = Field(..., min_length=6, max_length=100)
    role: str = Field(..., max_length=50)
    name: str = Field(..., min_length=2, max_length=100)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        if "@" not in v:
            raise ValueError("Invalid email format")
        return v

    @field_validator("role")
    @classmethod
    def validate_role(cls, v):
        if v not in ["CITIZEN", "DRIVER", "ADMIN"]:
            raise ValueError("Invalid role specification")
        return v

# ----------------- Endpoints -----------------

@app.post("/api/auth/register")
def register(email: str = Form(...), password: str = Form(...), name: str = Form(...), db: Session = Depends(get_db)):
    try:
        UserRegister(email=email, password=password, name=name)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=e.errors()[0]["msg"])

    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = get_password_hash(password)
    user = User(email=email, password_hash=hashed_password, role="CITIZEN", name=name, eco_points=150)
    db.add(user)
    db.commit()
    return {"message": "User created successfully"}

@app.post("/api/admin/create_user")
def admin_create_user(
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    name: str = Form(...),
    admin: User = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    try:
        AdminCreateUser(email=email, password=password, role=role, name=name)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=e.errors()[0]["msg"])

    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = get_password_hash(password)
    user = User(email=email, password_hash=hashed_password, role=role, name=name, eco_points=0 if role != "CITIZEN" else 150)
    db.add(user)
    db.commit()
    return {"message": f"User with role {role} created successfully"}



@app.post("/api/auth/login")
@limiter.limit("5/minute")  # Protect against brute-force attacks
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    
    access_token = create_access_token(data={"sub": user.email, "role": user.role})
    refresh_token = create_refresh_token(data={"sub": user.email})
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user_id": user.id,
        "name": user.name,
        "role": user.role,
        "eco_points": user.eco_points
    }

@app.post("/api/auth/refresh")
def refresh_token(refresh_token_str: str = Form(...), db: Session = Depends(get_db)):
    """
    Accepts a refresh_token, validates it, and returns a new short-lived access_token.
    The Flutter app should call this on 401 errors before redirecting to login.
    """
    payload = decode_refresh_token(refresh_token_str)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token. Please log in again.")
    email = payload.get("sub")
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    new_access_token = create_access_token(data={"sub": user.email, "role": user.role})
    return {"access_token": new_access_token, "token_type": "bearer"}

class ReportIssueValidation(BaseModel):
    zone: str = Field(..., min_length=1, max_length=100)
    area: str = Field(..., min_length=1, max_length=100)
    lat: float = Field(..., ge=-90.0, le=90.0)
    lng: float = Field(..., ge=-180.0, le=180.0)

@app.post("/api/citizen/report_issue")
@limiter.limit("10/minute")
async def report_issue(
    request: Request,
    zone: str = Form(...),
    area: str = Form(...),
    lat: float = Form(...),
    lng: float = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        ReportIssueValidation(zone=zone, area=area, lat=lat, lng=lng)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=e.errors()[0]["msg"])

    if current_user.role != "CITIZEN":
        raise HTTPException(status_code=403, detail="Only citizens can report waste")


    # Call AI Engine for Classification
    ai_analysis = {"waste_type": "Mixed", "severity_level": "High"}
    try:
        file_bytes = await file.read()
        await file.seek(0) # Reset stream pointer
        files = {"file": (file.filename, file_bytes, file.content_type)}
        async with httpx.AsyncClient() as client:
            ai_response = await client.post(f"{AI_ENGINE_URL}/ai/classify_waste", files=files, timeout=5.0)
            if ai_response.status_code == 200:
                ai_analysis = ai_response.json()
    except Exception as e:
        print(f"AI Engine Error: {e}")

    new_complaint = Complaint(
        citizen_id=current_user.id,
        zone=zone,
        area=area,
        waste_type=ai_analysis.get("waste_type", "Mixed"),
        severity_level=ai_analysis.get("severity_level", "High"),
        lat=lat,
        lng=lng
    )
    db.add(new_complaint)
    current_user.eco_points += 15
    db.commit()
    db.refresh(new_complaint)
    
    return {
        "message": "Report logged", 
        "complaint_id": new_complaint.id, 
        "points": current_user.eco_points,
        "ai_analysis": ai_analysis
    }

@app.get("/api/citizen/my_reports")
def my_reports(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    reports = db.query(Complaint).filter(Complaint.citizen_id == current_user.id).all()
    return reports

@app.get("/api/citizen/cleanliness_score")
def cleanliness_score(db: Session = Depends(get_db)):
    """
    Calculates a live cleanliness score (0-100) for the city.
    Score = (Resolved / Total) * 100, or 100 if no complaints exist.
    This replaces the hardcoded '88%' in the Citizen Dashboard.
    """
    total = db.query(Complaint).count()
    if total == 0:
        return {"score": 100, "label": "Perfect", "message": "No complaints reported. City is clean!"}
    resolved = db.query(Complaint).filter(Complaint.status == "RESOLVED").count()
    score = round((resolved / total) * 100)
    label = "Excellent" if score >= 80 else "Good" if score >= 60 else "Needs Attention" if score >= 40 else "Critical"
    return {
        "score": score,
        "label": label,
        "message": f"{resolved} of {total} complaints resolved.",
        "total": total,
        "resolved": resolved
    }

@app.post("/api/driver/update_location")
async def update_location(lat: float = Form(...), lng: float = Form(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "DRIVER":
        raise HTTPException(status_code=403, detail="Not a valid driver")
    
    loc = db.query(DriverLocation).filter(DriverLocation.driver_id == current_user.id).first()
    if loc:
        loc.lat = lat
        loc.lng = lng
        loc.updated_at = datetime.utcnow()
    else:
        loc = DriverLocation(driver_id=current_user.id, lat=lat, lng=lng)
        db.add(loc)
    db.commit()

    # Broadcast to all connected Admins via WebSocket
    await manager.broadcast({
        "type": "LOCATION_UPDATE",
        "driver_id": current_user.id,
        "name": current_user.name,
        "lat": lat,
        "lng": lng
    })

    return {"status": "Updated"}

# ----------------- WebSockets -----------------
@app.websocket("/ws/admin")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text() # Keep alive
    except WebSocketDisconnect:
        await manager.disappearance(websocket)

# ----------------- Global Exception Handler -----------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("unhandled_server_exception", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={"message": "Internal Server Error", "detail": str(exc)},
    )


@app.get("/api/driver/active_complaints")
def active_complaints(db: Session = Depends(get_db)):
    reports = db.query(Complaint).filter(Complaint.status == "PENDING").all()
    return reports

@app.get("/api/admin/dashboard_stats")
def dashboard_stats(admin: User = Depends(verify_admin), db: Session = Depends(get_db)):
    total_complaints = db.query(Complaint).count()
    fleet = db.query(DriverLocation).all()
    fleet_data = [{"driver_id": f.driver_id, "lat": f.lat, "lng": f.lng} for f in fleet]
    return {
        "active_complaints": total_complaints,
        "active_fleet_count": len(fleet),
        "fleet": fleet_data,
        "avg_delay_min": 18,
        "ai_alerts": 3
    }

class CompletePickupValidation(BaseModel):
    complaint_id: int = Field(..., gt=0)

@app.post("/api/driver/complete_pickup")
async def complete_pickup(
    complaint_id: int = Form(...),
    proof_photo: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        CompletePickupValidation(complaint_id=complaint_id)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=e.errors()[0]["msg"])

    if current_user.role != "DRIVER":
        raise HTTPException(status_code=403, detail="Not a valid driver")

    
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    
    driver_loc = db.query(DriverLocation).filter(DriverLocation.driver_id == current_user.id).first()
    if not driver_loc:
        raise HTTPException(status_code=400, detail="Driver location unknown. Please update GPS first.")
    
    # Geo-Fence: must be within 200 meters
    distance = haversine_distance(driver_loc.lat, driver_loc.lng, complaint.lat, complaint.lng)
    if distance > 200:
        raise HTTPException(
            status_code=400, 
            detail=f"Verification Failed: You are {round(distance)}m away. Move within 200m of the site."
        )

    # Fraud Detection: send proof image to AI Engine for validation
    fraud_result = {"is_fraud": False, "similarity": 0.0}
    try:
        proof_bytes = await proof_photo.read()
        await proof_photo.seek(0)
        files = {"proof_photo": (proof_photo.filename, proof_bytes, proof_photo.content_type)}
        data = {"complaint_id": str(complaint_id)}
        async with httpx.AsyncClient() as client:
            ai_resp = await client.post(
                f"{AI_ENGINE_URL}/ai/detect_fraud",
                files=files,
                data=data,
                timeout=5.0
            )
            if ai_resp.status_code == 200:
                fraud_result = ai_resp.json()
    except Exception as e:
        print(f"Fraud check skipped: {e}")

    if fraud_result.get("is_fraud", False):
        raise HTTPException(
            status_code=400,
            detail=f"Fraud Detected: Proof photo appears too similar to the complaint photo (similarity: {fraud_result.get('similarity', 0):.0%}). Re-photograph the cleaned area."
        )

    complaint.status = "RESOLVED"
    
    # Synchronize and complete the corresponding driver task
    task = db.query(DriverTask).filter(
        DriverTask.complaint_id == complaint_id,
        DriverTask.driver_id == current_user.id,
        DriverTask.status == "ASSIGNED"
    ).first()
    if task:
        task.status = "COMPLETED"
        task.completed_at = datetime.utcnow()

    db.commit()
    
    return {
        "status": "SUCCESS",
        "message": "Pickup verified and completed.",
        "distance": round(distance),
        "fraud_check": fraud_result
    }

@app.get("/api/admin/forecast")
async def get_forecast(admin: User = Depends(verify_admin)):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{AI_ENGINE_URL}/ai/forecast_waste", timeout=5.0)
            return response.json()
    except Exception as e:
        return {"error": str(e)}

# =================== NEW ENDPOINTS ===================

# --- Citizen Dashboard ---
@app.get("/api/citizen/dashboard")
def citizen_dashboard(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    total = db.query(Complaint).count()
    resolved = db.query(Complaint).filter(Complaint.status == "RESOLVED").count()
    score = round((resolved / total) * 100) if total > 0 else 100

    recent = db.query(Complaint).filter(
        Complaint.citizen_id == current_user.id
    ).order_by(Complaint.created_at.desc()).limit(5).all()

    return {
        "user_name": current_user.name,
        "eco_points": current_user.eco_points,
        "cleanliness_score": score,
        "total_reports": db.query(Complaint).filter(Complaint.citizen_id == current_user.id).count(),
        "pending_reports": db.query(Complaint).filter(Complaint.citizen_id == current_user.id, Complaint.status == "PENDING").count(),
        "recent_reports": [
            {"id": r.id, "area": r.area, "zone": r.zone, "waste_type": r.waste_type, "status": r.status, "created_at": str(r.created_at)}
            for r in recent
        ]
    }

# --- Rewards & Leaderboard ---
@app.get("/api/citizen/rewards")
def get_rewards(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rewards = db.query(Reward).filter(Reward.is_active == 1).all()
    top_users = db.query(User).filter(User.role == "CITIZEN").order_by(User.eco_points.desc()).limit(5).all()
    user_rank_list = db.query(User).filter(User.role == "CITIZEN").order_by(User.eco_points.desc()).all()
    user_rank = next((i + 1 for i, u in enumerate(user_rank_list) if u.id == current_user.id), 0)

    return {
        "eco_points": current_user.eco_points,
        "tier": "Champion" if current_user.eco_points >= 2000 else "Elite Recycler" if current_user.eco_points >= 1000 else "Green Starter",
        "tier_progress": min(100, round((current_user.eco_points % 1000) / 10)),
        "next_tier_points": (((current_user.eco_points // 1000) + 1) * 1000) - current_user.eco_points,
        "co2_saved_kg": round(current_user.eco_points * 0.034, 1),
        "waste_sorted_kg": round(current_user.eco_points * 0.148, 1),
        "rewards": [
            {"id": r.id, "title": r.title, "provider": r.provider, "category": r.category, "points_cost": r.points_cost, "image_url": r.image_url}
            for r in rewards
        ],
        "leaderboard": [
            {"rank": i + 1, "name": u.name, "points": u.eco_points}
            for i, u in enumerate(top_users)
        ],
        "user_rank": user_rank
    }

@app.post("/api/citizen/redeem_reward")
def redeem_reward(reward_id: int = Form(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    reward = db.query(Reward).filter(Reward.id == reward_id).first()
    if not reward:
        raise HTTPException(status_code=404, detail="Reward not found")
    if current_user.eco_points < reward.points_cost:
        raise HTTPException(status_code=400, detail="Insufficient EcoPoints")
    current_user.eco_points -= reward.points_cost
    db.add(RewardRedemption(user_id=current_user.id, reward_id=reward_id))
    db.commit()
    return {"message": "Reward redeemed!", "remaining_points": current_user.eco_points}

# --- Heatmap Data (Citizen) ---
@app.get("/api/citizen/heatmap_data")
def citizen_heatmap(db: Session = Depends(get_db)):
    complaints = db.query(Complaint).filter(Complaint.status != "RESOLVED").all()
    bins = []
    for c in complaints:
        fill = 95 if c.severity_level == "High" else 65 if c.severity_level == "Medium" else 30
        level = "critical" if fill > 80 else "attention" if fill > 50 else "clean"
        bins.append({"id": c.id, "area": c.area, "zone": c.zone, "lat": c.lat, "lng": c.lng, "fill_percent": fill, "level": level})
    return {"bins": bins}

# --- Driver Dashboard ---
@app.get("/api/driver/dashboard")
def driver_dashboard(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "DRIVER":
        raise HTTPException(status_code=403, detail="Driver only")
    tasks = db.query(DriverTask).filter(DriverTask.driver_id == current_user.id).all()
    assigned = [t for t in tasks if t.status == "ASSIGNED"]
    completed = [t for t in tasks if t.status == "COMPLETED"]
    return {
        "driver_name": current_user.name,
        "total_assigned": len(assigned),
        "completed_today": len(completed),
        "total_tasks": len(tasks),
        "vehicle_id": "TRK-9902",
        "sector": "South Sector",
        "next_pickup_km": assigned[0].distance_km if assigned else 0,
    }

# --- Assigned Pickups ---
@app.get("/api/driver/assigned_tasks")
def assigned_tasks(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "DRIVER":
        raise HTTPException(status_code=403, detail="Driver only")
    tasks = db.query(DriverTask).filter(DriverTask.driver_id == current_user.id, DriverTask.status == "ASSIGNED").order_by(DriverTask.priority).all()
    return [
        {"id": t.id, "complaint_id": t.complaint_id, "priority": t.priority, "waste_type": t.waste_type, "address": t.address, "bin_fill_percent": t.bin_fill_percent, "distance_km": t.distance_km, "status": t.status}
        for t in tasks
    ]

# --- Driver Performance ---
@app.get("/api/driver/performance")
def driver_performance(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "DRIVER":
        raise HTTPException(status_code=403, detail="Driver only")
    tasks = db.query(DriverTask).filter(DriverTask.driver_id == current_user.id).all()
    completed = [t for t in tasks if t.status == "COMPLETED"]
    total = len(tasks)
    return {
        "driver_name": current_user.name,
        "total_pickups": total,
        "completed": len(completed),
        "efficiency": round((len(completed) / total) * 100, 1) if total > 0 else 0,
        "rank": 3,
        "weekly_pickups": [12, 15, 10, 18, 14, 8, 16],
        "reward_tier": "Gold",
        "km_saved": 12.4,
    }

# --- Admin Expanded Dashboard ---
@app.get("/api/admin/overview")
def admin_overview(admin: User = Depends(verify_admin), db: Session = Depends(get_db)):
    total_complaints = db.query(Complaint).count()
    pending = db.query(Complaint).filter(Complaint.status == "PENDING").count()
    resolved = db.query(Complaint).filter(Complaint.status == "RESOLVED").count()
    fleet_count = db.query(DriverLocation).count()
    active_incidents = db.query(DumpingIncident).filter(DumpingIncident.status == "ACTIVE").count()
    return {
        "total_complaints": total_complaints,
        "pending_complaints": pending,
        "resolved_complaints": resolved,
        "collection_rate": round((resolved / total_complaints) * 100, 1) if total_complaints > 0 else 0,
        "active_fleet": fleet_count,
        "avg_response_hours": 2.4,
        "active_incidents": active_incidents,
        "ai_alerts": 3,
    }

# --- Admin Waste Heatmap ---
@app.get("/api/admin/waste_heatmap")
def admin_heatmap(admin: User = Depends(verify_admin), db: Session = Depends(get_db)):
    complaints = db.query(Complaint).all()
    zones = {}
    for c in complaints:
        z = c.zone or "Unknown"
        if z not in zones:
            zones[z] = {"zone": z, "total": 0, "pending": 0, "lat": c.lat, "lng": c.lng}
        zones[z]["total"] += 1
        if c.status == "PENDING":
            zones[z]["pending"] += 1
    return {"zones": list(zones.values())}

# --- Contractor Performance ---
@app.get("/api/admin/contractor_stats")
def contractor_stats(admin: User = Depends(verify_admin), db: Session = Depends(get_db)):
    contractors_list = db.query(Contractor).all()
    return {
        "avg_response_time": 2.4,
        "overall_completion_rate": 98.2,
        "citizen_satisfaction": 4.8,
        "total_active_contractors": len(contractors_list),
        "contractors": [
            {"id": c.id, "name": c.name, "completion_rate": c.completion_rate, "satisfaction_score": c.satisfaction_score, "response_time_hours": c.response_time_hours, "active_drivers": c.active_drivers}
            for c in contractors_list
        ]
    }

# --- Illegal Dumping ---
@app.get("/api/admin/illegal_dumping")
def illegal_dumping(admin: User = Depends(verify_admin), db: Session = Depends(get_db)):
    incidents = db.query(DumpingIncident).all()
    active = [i for i in incidents if i.status == "ACTIVE"]
    high_risk = [i for i in active if i.severity == "HIGH"]
    return {
        "total_incidents": len(incidents),
        "active_incidents": len(active),
        "high_risk_count": len(high_risk),
        "avg_clear_hours": 2.4,
        "incidents": [
            {"id": i.id, "zone": i.zone, "cluster_id": i.cluster_id, "description": i.description, "severity": i.severity, "predicted_culprit": i.predicted_culprit, "common_time": i.common_time, "confidence": i.confidence, "lat": i.lat, "lng": i.lng, "status": i.status, "detected_at": str(i.detected_at)}
            for i in incidents
        ]
    }

@app.post("/api/admin/dispatch_team")
def dispatch_team(incident_id: int = Form(...), admin: User = Depends(verify_admin), db: Session = Depends(get_db)):
    incident = db.query(DumpingIncident).filter(DumpingIncident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    incident.status = "DISPATCHED"
    incident.dispatched_at = datetime.utcnow()
    db.commit()
    return {"message": "Team dispatched", "incident_id": incident.id, "zone": incident.zone}


# --- User Profile ---
@app.get("/api/auth/profile")
def get_profile(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "role": current_user.role,
        "eco_points": current_user.eco_points,
    }

