from fastapi import WebSocket
from typing import Dict, List
import json


class ConnectionManager:
    def __init__(self):
        # Maps driver_id -> list of active WebSocket connections
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, driver_id: int):
        await websocket.accept()

        connections = self.active_connections.setdefault(driver_id, [])

        # Prevent duplicate registration of the same socket.
        if not any(connection is websocket for connection in connections):
            connections.append(websocket)

    def disconnect(self, driver_id: int, websocket: WebSocket):
        connections = self.active_connections.get(driver_id)

        if not connections:
            return

        # Remove only the exact socket that disconnected.
        remaining = [
            connection
            for connection in connections
            if connection is not websocket
        ]

        if remaining:
            self.active_connections[driver_id] = remaining
        else:
            self.active_connections.pop(driver_id, None)

    async def send_personal_message(self, message: str, driver_id: int):
        # Use a snapshot so connection changes during delivery are safe.
        connections = list(self.active_connections.get(driver_id, []))

        for websocket in connections:
            try:
                await websocket.send_text(message)
            except Exception:
                # Remove only the socket whose delivery failed.
                self.disconnect(driver_id, websocket)

    async def notify_driver_new_task(self, driver_id: int, complaint_id: int):
        message = json.dumps({
            "type": "NEW_TASK",
            "complaint_id": complaint_id,
            "message": "You have been assigned a new pickup task!"
        })

        await self.send_personal_message(message, driver_id)


manager = ConnectionManager()
