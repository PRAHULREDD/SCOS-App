import os
import time
import uuid
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from app.api.v1 import auth, citizens, drivers, admin
from app.websocket.manager import manager
from app.core.auth import decode_access_token

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """R6: Modern lifespan replaces deprecated @app.on_event('startup')."""
    from app.db.database import engine, DATABASE_URL
    from app.models.domain import Base
    if "sqlite" in DATABASE_URL:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("SQLite database tables ensured.")
    yield
    # shutdown: nothing to clean up currently


app = FastAPI(title="SCOS Async Enterprise API", version="2.0.0", lifespan=lifespan)

# CORS Middleware
# allow_origins=["*"] is incompatible with allow_credentials=True in browsers.
# Auth uses Authorization: Bearer header (not cookies), so credentials=False is correct.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request Metrics Middleware
@app.middleware("http")
async def add_metrics_and_log(request: Request, call_next):
    request_id = str(uuid.uuid4())
    start_time = time.time()

    response = await call_next(request)

    duration = time.time() - start_time
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = str(duration)

    logger.info(
        f"Method: {request.method} Path: {request.url.path} "
        f"Status: {response.status_code} Duration: {duration:.4f}s "
        f"ReqID: {request_id}"
    )

    return response


# Include Routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(citizens.router, prefix="/api/citizen", tags=["Citizen"])
app.include_router(drivers.router, prefix="/api/driver", tags=["Driver"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])

# Mount static files (Frontend)
static_path = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_path):
    app.mount("/app", StaticFiles(directory=static_path), name="static")
else:
    logger.warning(f"Static directory not found at {static_path}")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "2.0.0"}


@app.get("/", include_in_schema=False)
async def root_redirect():
    """Redirect root to the frontend app."""
    return RedirectResponse(url="/app/index.html")


@app.websocket("/api/ws/driver/{driver_id}")
async def websocket_driver_endpoint(
    websocket: WebSocket,
    driver_id: int,
    token: str = Query(default=None)
):
    """
    WebSocket endpoint for real-time driver notifications.

    Authentication: caller must pass ?token=<access_token> in the URL.
    The authenticated user must be the same driver as driver_id.
    """
    # Reject unauthenticated connections immediately
    if not token:
        await websocket.close(code=4001, reason="Missing authentication token")
        return

    payload = decode_access_token(token)
    if not payload:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    # Must be a DRIVER
    if payload.get("role") != "DRIVER":
        await websocket.close(code=4003, reason="Driver role required")
        return

    # Verify the connecting driver matches the requested driver_id.
    # We do this by checking the sub (email) and fetching the user.
    from app.db.database import SessionLocal
    from app.repositories.user_repo import user_repo as _user_repo
    async with SessionLocal() as db:
        user = await _user_repo.get_by_email(db, payload.get("sub"))

    if not user or user.id != driver_id:
        await websocket.close(code=4003, reason="Driver ID mismatch — unauthorized")
        return

    await manager.connect(websocket, driver_id)
    logger.info(f"Driver {driver_id} WebSocket connected")

    try:
        while True:
            # Keep connection alive; handle ping/pong or any client messages
            data = await websocket.receive_text()
            # Echo back a pong if client sends "ping"
            if data.strip() == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(driver_id)
        logger.info(f"Driver {driver_id} WebSocket disconnected")
