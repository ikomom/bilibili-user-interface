from typing import Any
from uuid import UUID

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: dict[UUID, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, subscription_id: UUID) -> None:
        await websocket.accept()
        if subscription_id not in self.active_connections:
            self.active_connections[subscription_id] = []
        self.active_connections[subscription_id].append(websocket)

    def disconnect(self, websocket: WebSocket, subscription_id: UUID) -> None:
        if subscription_id in self.active_connections:
            self.active_connections[subscription_id].remove(websocket)

    async def broadcast(self, subscription_id: UUID, message: dict[str, Any]) -> None:
        if subscription_id not in self.active_connections:
            return
        dead_connections: list[WebSocket] = []
        for connection in self.active_connections[subscription_id]:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.append(connection)
        for conn in dead_connections:
            self.disconnect(conn, subscription_id)


ws_manager = ConnectionManager()
