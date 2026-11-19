"""
SCOS Driver WebSocket Reconnection & Resilience Backend Test Suite
Phase 5 Verification Suite

Verifies:
1. Valid driver authentication handshake and connection acceptance.
2. Missing token rejection (ASGI code 4001).
3. Invalid or expired token rejection (ASGI code 4001).
4. Role authorization guards: CITIZEN and ADMIN roles rejected (ASGI code 4003).
5. Driver ID authorization guard: ID mismatch rejected (ASGI code 4003).
6. NEW_TASK broadcast message delivery via manager.notify_driver_new_task.
7. Multi-socket preservation: multiple concurrent sockets for one driver receive broadcasts.
8. Failed-socket cleanup: disconnecting one socket removes only that socket and preserves others.
"""
import os
import sys
import json
import pytest
import pytest_asyncio
from unittest.mock import patch
from datetime import datetime, timezone, timedelta

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from main import app
from app.websocket.manager import manager
from app.models.domain import Base, User
from app.core.auth import create_access_token, get_password_hash

os.environ["SECRET_KEY"] = "testsecretkeytestsecretkeytestsecretkey"
os.environ["ENVIRONMENT"] = "testing"

SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///./test_websocket.db"
engine = create_async_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(class_=AsyncSession, autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)


@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_test_db():
    # Ensure in-memory active_connections is clean before each test
    manager.active_connections.clear()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    # Seed test users: Driver 1, Driver 2, Citizen, Admin
    async with TestingSessionLocal() as db:
        driver1 = User(
            id=101,
            email="driver101@scos.local",
            password_hash=get_password_hash("pass123"),
            name="Driver One",
            role="DRIVER"
        )
        driver2 = User(
            id=102,
            email="driver102@scos.local",
            password_hash=get_password_hash("pass123"),
            name="Driver Two",
            role="DRIVER"
        )
        citizen = User(
            id=201,
            email="citizen201@scos.local",
            password_hash=get_password_hash("pass123"),
            name="Citizen One",
            role="CITIZEN"
        )
        admin = User(
            id=301,
            email="admin301@scos.local",
            password_hash=get_password_hash("pass123"),
            name="Admin One",
            role="ADMIN"
        )
        db.add_all([driver1, driver2, citizen, admin])
        await db.commit()

    try:
        yield
    finally:
        # Clean up any lingering connections
        manager.active_connections.clear()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def client():
    with patch("app.db.database.SessionLocal", TestingSessionLocal):
        with TestClient(app) as c:
            yield c


def test_ws_driver_connect_success(client):
    """Test that a valid DRIVER token connects and can ping/pong."""
    token = create_access_token({"sub": "driver101@scos.local", "role": "DRIVER", "user_id": 101})

    with client.websocket_connect(f"/api/ws/driver/101?token={token}") as ws:
        assert 101 in manager.active_connections
        assert len(manager.active_connections[101]) == 1

        # Test bidirectional communication (ping / pong)
        ws.send_text("ping")
        data = ws.receive_text()
        assert data == "pong"

    # After exiting context, socket is disconnected
    assert 101 not in manager.active_connections


def test_ws_missing_token_rejection(client):
    """Test that connection without a token query parameter is closed with code 4001."""
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/ws/driver/101"):
            pass

    assert exc_info.value.code == 4001


def test_ws_invalid_token_rejection(client):
    """Test that connection with a malformed/invalid token is closed with code 4001."""
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/ws/driver/101?token=invalid.jwt.token"):
            pass

    assert exc_info.value.code == 4001


def test_ws_expired_token_rejection(client):
    """Test that connection with an expired token is closed with code 4001."""
    expired_token = create_access_token(
        data={"sub": "driver101@scos.local", "role": "DRIVER", "user_id": 101},
        expires_delta=timedelta(seconds=-60)
    )

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/api/ws/driver/101?token={expired_token}") as ws:
            pass

    assert exc_info.value.code == 4001


def test_ws_citizen_role_rejection(client):
    """Test that a valid token for a CITIZEN role is rejected with code 4003."""
    citizen_token = create_access_token({"sub": "citizen201@scos.local", "role": "CITIZEN", "user_id": 201})

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/api/ws/driver/201?token={citizen_token}") as ws:
            pass

    assert exc_info.value.code == 4003


def test_ws_admin_role_rejection(client):
    """Test that a valid token for an ADMIN role is rejected with code 4003."""
    admin_token = create_access_token({"sub": "admin301@scos.local", "role": "ADMIN", "user_id": 301})

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/api/ws/driver/301?token={admin_token}") as ws:
            pass

    assert exc_info.value.code == 4003


def test_ws_driver_id_mismatch_rejection(client):
    """Test that Driver 101 connecting to driver 102 route is rejected with code 4003."""
    driver1_token = create_access_token({"sub": "driver101@scos.local", "role": "DRIVER", "user_id": 101})

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/api/ws/driver/102?token={driver1_token}") as ws:
            pass

    assert exc_info.value.code == 4003


@pytest.mark.asyncio
async def test_ws_broadcast_new_task_delivery(client):
    """Test that manager.notify_driver_new_task dispatches correct JSON to active driver."""
    token = create_access_token({"sub": "driver101@scos.local", "role": "DRIVER", "user_id": 101})

    with client.websocket_connect(f"/api/ws/driver/101?token={token}") as ws:
        # Trigger notification from connection manager
        await manager.notify_driver_new_task(driver_id=101, complaint_id=55)

        raw_message = ws.receive_text()
        data = json.loads(raw_message)

        assert data["type"] == "NEW_TASK"
        assert data["complaint_id"] == 55
        assert "You have been assigned a new pickup task!" in data["message"]


@pytest.mark.asyncio
async def test_ws_multi_socket_preservation(client):
    """Test that multiple sockets for the same driver both receive broadcasts."""
    token = create_access_token({"sub": "driver101@scos.local", "role": "DRIVER", "user_id": 101})

    with client.websocket_connect(f"/api/ws/driver/101?token={token}") as ws1:
        with client.websocket_connect(f"/api/ws/driver/101?token={token}") as ws2:
            assert len(manager.active_connections[101]) == 2

            # Dispatch notification
            await manager.notify_driver_new_task(driver_id=101, complaint_id=88)

            msg1 = json.loads(ws1.receive_text())
            msg2 = json.loads(ws2.receive_text())

            assert msg1["complaint_id"] == 88
            assert msg2["complaint_id"] == 88


@pytest.mark.asyncio
async def test_ws_failed_socket_cleanup(client):
    """Test that disconnecting one socket removes only that socket and preserves remaining connections."""
    token = create_access_token({"sub": "driver101@scos.local", "role": "DRIVER", "user_id": 101})

    with client.websocket_connect(f"/api/ws/driver/101?token={token}") as ws_persisting:
        # Open and immediately exit second socket
        with client.websocket_connect(f"/api/ws/driver/101?token={token}") as ws_closing:
            assert len(manager.active_connections[101]) == 2

        # ws_closing has exited; ws_persisting must still be registered
        assert len(manager.active_connections[101]) == 1

        # Dispatch notification to remaining socket
        await manager.notify_driver_new_task(driver_id=101, complaint_id=99)
        msg = json.loads(ws_persisting.receive_text())
        assert msg["complaint_id"] == 99

    # After ws_persisting exits, driver has 0 active connections
    assert 101 not in manager.active_connections
