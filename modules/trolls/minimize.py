import ctypes

def minimize_all():
    """Minimizes all windows."""
    ctypes.windll.user32.PostMessageW(0xFFFF, 0x111, 419, 0)
