import ctypes, time, threading, random

def melt_screen(duration=15):
    """Classic GDI Screen Melting Effect."""
    def _melt():
        try:
            user32 = ctypes.windll.user32
            gdi32 = ctypes.windll.gdi32
            w = user32.GetSystemMetrics(0)
            h = user32.GetSystemMetrics(1)
            hdc = user32.GetDC(0)
            end_time = time.time() + duration
            while time.time() < end_time:
                x = random.randint(0, w)
                y = random.randint(0, 10) # start from top
                width = random.randint(50, 200)
                # Copy a block of the screen downwards
                gdi32.BitBlt(hdc, x, y + 2, width, h, hdc, x, y, 0x00CC0020) # SRCCOPY
                time.sleep(0.01)
            user32.ReleaseDC(0, hdc)
        except: pass
    threading.Thread(target=_melt, daemon=True).start()
