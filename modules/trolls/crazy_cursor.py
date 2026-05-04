import threading, time, random

def crazy_cursor(duration=10):
    """Moves the mouse cursor randomly for a set duration."""
    def _crazy():
        try:
            import pyautogui
            deadline = time.time() + duration
            w, h = pyautogui.size()
            while time.time() < deadline:
                pyautogui.moveTo(random.randint(0, w), random.randint(0, h), duration=0.05)
        except: pass

    threading.Thread(target=_crazy, daemon=True).start()
