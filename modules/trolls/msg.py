import ctypes, threading

def show_msg(text):
    """Independent message box utility."""
    def _box():
        ctypes.windll.user32.MessageBoxW(0, text, "System Intelligence", 0x40 | 0x0)
    threading.Thread(target=_box, daemon=True).start()
