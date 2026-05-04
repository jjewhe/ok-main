import ctypes, time, threading

_cursor_forced = False

def _cursor_lock_loop():
    while _cursor_forced:
        w = ctypes.windll.user32.GetSystemMetrics(0)
        h = ctypes.windll.user32.GetSystemMetrics(1)
        ctypes.windll.user32.SetCursorPos(w // 2, h // 2)
        time.sleep(0.02)

def lock_cursor():
    global _cursor_forced
    if not _cursor_forced:
        _cursor_forced = True
        threading.Thread(target=_cursor_lock_loop, daemon=True).start()

def unlock_cursor():
    global _cursor_forced
    _cursor_forced = False
