import os
import time
import uuid
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1 import auth, citizens, drivers, admin

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="SCOS Async Enterprise API", version="2.0.0")

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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

# Mount static files (Frontend MVP)
static_path = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_path):
    app.mount("/app", StaticFiles(directory=static_path), name="static")
else:
    logger.warning(f"Static directory not found at {static_path}")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "2.0.0"}

from fastapi import WebSocket, WebSocketDisconnect
from app.websocket.manager import manager

@app.websocket("/api/ws/driver/{driver_id}")
async def websocket_driver_endpoint(websocket: WebSocket, driver_id: int):
    await manager.connect(websocket, driver_id)
    try:
        while True:
            # We just need to keep the connection alive
            # If the client sends a message, we can just log it or ignore
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(driver_id)
