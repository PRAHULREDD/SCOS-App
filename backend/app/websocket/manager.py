from fastapi import WebSocket
from typing import Dict, List
import json

class ConnectionManager:
    def __init__(self):
        # Maps driver_id -> WebSocket
        self.active_connections: Dict[int, WebSocket] = {}

    async def connect(self, websocket: WebSocket, driver_id: int):
        await websocket.accept()
        self.active_connections[driver_id] = websocket

    def disconnect(self, driver_id: int):
        if driver_id in self.active_connections:
            del self.active_connections[driver_id]

    async def send_personal_message(self, message: str, driver_id: int):
        if driver_id in self.active_connections:
            try:
                await self.active_connections[driver_id].send_text(message)
            except Exception:
                self.disconnect(driver_id)

    async def notify_driver_new_task(self, driver_id: int, complaint_id: int):
        message = json.dumps({
            "type": "NEW_TASK",
            "complaint_id": complaint_id,
            "message": "You have been assigned a new pickup task!"
        })
        await self.send_personal_message(message, driver_id)

manager = ConnectionManager()
