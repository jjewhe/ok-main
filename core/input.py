import ctypes
from ctypes import wintypes

# Low-level Windows API constants
INPUT_MOUSE    = 0
INPUT_KEYBOARD = 1
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_MOVE     = 0x0001
MOUSEEVENTF_LEFTDOWN  = 0x0002
MOUSEEVENTF_LEFTUP    = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP   = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP   = 0x0040
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP       = 0x0002

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]

class INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]

class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", INPUT_UNION)]

# Complete virtual key map (browser key name -> VK code + extended flag)
# Format: key_name -> (vk_code, is_extended)
VK_MAP = {
    # Control keys
    "Backspace": (0x08, False), "Tab": (0x09, False), "Enter": (0x0D, False),
    "Shift": (0x10, False), "Control": (0x11, False), "Alt": (0x12, False),
    "Pause": (0x13, False), "CapsLock": (0x14, False),
    "Escape": (0x1B, False), " ": (0x20, False),
    "PageUp": (0x21, True), "PageDown": (0x22, True),
    "End": (0x23, True), "Home": (0x24, True),
    "ArrowLeft": (0x25, True), "ArrowUp": (0x26, True),
    "ArrowRight": (0x27, True), "ArrowDown": (0x28, True),
    "Insert": (0x2D, True), "Delete": (0x2E, True),
    # Windows / Meta key (EXTENDED)
    "Meta": (0x5B, True), "OS": (0x5B, True),
    "ContextMenu": (0x5D, True),
    # Numpad
    "NumLock": (0x90, True),
    # Function keys
    "F1": (0x70, False), "F2": (0x71, False), "F3": (0x72, False), "F4": (0x73, False),
    "F5": (0x74, False), "F6": (0x75, False), "F7": (0x76, False), "F8": (0x77, False),
    "F9": (0x78, False), "F10": (0x79, False), "F11": (0x7A, False), "F12": (0x7B, False),
    # Modifier aliases
    "ShiftLeft": (0xA0, False), "ShiftRight": (0xA1, False),
    "ControlLeft": (0xA2, False), "ControlRight": (0xA3, True),
    "AltLeft": (0xA4, False), "AltRight": (0xA5, True), "AltGraph": (0xA5, True),
    # Scroll lock / print screen
    "ScrollLock": (0x91, False), "PrintScreen": (0x2C, False),
    # Media keys (extended)
    "AudioVolumeMute": (0xAD, True), "AudioVolumeDown": (0xAE, True),
    "AudioVolumeUp": (0xAF, True), "MediaTrackNext": (0xB0, True),
    "MediaTrackPrevious": (0xB1, True), "MediaStop": (0xB2, True),
    "MediaPlayPause": (0xB3, True),
    # Semicolon / apostrophe etc (common)
    ";": (0xBA, False), "=": (0xBB, False), ",": (0xBC, False),
    "-": (0xBD, False), ".": (0xBE, False), "/": (0xBF, False),
    "`": (0xC0, False), "[": (0xDB, False), "\\": (0xDC, False),
    "]": (0xDD, False), "'": (0xDE, False),
}

class InputHub:
    def __init__(self):
        self.user32 = ctypes.windll.user32
        # Set process as DPI aware to ensure real physical coordinates
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except:
            try: self.user32.SetProcessDPIAware()
            except: pass
        self.screen_width  = self.user32.GetSystemMetrics(0)
        self.screen_height = self.user32.GetSystemMetrics(1)

    def mouse_move_and_click(self, x, y, btn="left", down=True):
        """Atomic move-and-click using mouse_event for maximum compatibility."""
        self.mouse_move(x, y)
        self.mouse_click(btn, down)
        return True

    def click_full(self, x, y, btn="left"):
        """Full click: move + down + up in one call. Most reliable for remote control."""
        import time
        self.mouse_move(x, y)
        self.mouse_click(btn, True)   # down
        time.sleep(0.05)              # 50ms delay so Windows doesn't drop the click
        self.mouse_click(btn, False)  # up
        return True

    def mouse_move(self, x, y):
        """Move mouse to absolute physical pixel."""
        vx = self.user32.GetSystemMetrics(76)
        vy = self.user32.GetSystemMetrics(77)
        vw = self.user32.GetSystemMetrics(78)
        vh = self.user32.GetSystemMetrics(79)
        if vw <= 0: vw = self.screen_width
        if vh <= 0: vh = self.screen_height
        
        # Direct pixel-accurate move for primary-relative coordinates
        self.user32.SetCursorPos(x, y)
        
        # MOUSEEVENTF_ABSOLUTE (0x8000) | MOUSEEVENTF_MOVE (0x0001) | MOUSEEVENTF_VIRTUALDESK (0x4000)
        norm_x = int((x - vx) * 65535 / (vw - 1))
        norm_y = int((y - vy) * 65535 / (vh - 1))
        
        # Safety clamping
        norm_x = max(0, min(65535, norm_x))
        norm_y = max(0, min(65535, norm_y))
        
        # Debug trace
        try:
            with open(os.path.join(os.environ.get("TEMP", ""), "mrl_debug.txt"), "a") as f:
                f.write(f"[{time.strftime('%H:%M:%S')}] [INPUT] Move: {x}, {y} (norm {norm_x}, {norm_y})\n")
        except: pass
        self.user32.mouse_event(0x8000 | 0x0001 | 0x4000, norm_x, norm_y, 0, 0)

    def mouse_click(self, btn="left", down=True):
        """Send click using mouse_event."""
        if btn == "left":
            flags = 0x0002 if down else 0x0004 # LEFTDOWN / LEFTUP
        elif btn == "right":
            flags = 0x0008 if down else 0x0010 # RIGHTDOWN / RIGHTUP
        else:
            flags = 0x0020 if down else 0x0040 # MIDDLEDOWN / MIDDLEUP
            
        try:
            with open(os.path.join(os.environ.get("TEMP", ""), "mrl_debug.txt"), "a") as f:
                f.write(f"[{time.strftime('%H:%M:%S')}] [INPUT] Click: {btn} {'DOWN' if down else 'UP'} (flags {hex(flags)})\n")
        except: pass
        self.user32.mouse_event(flags, 0, 0, 0, 0)

    def mouse_scroll(self, delta):
        """Scroll using mouse_event (0x0800 = WHEEL)."""
        self.user32.mouse_event(0x0800, 0, 0, int(delta * 120), 0)

    def key_event(self, key, down=True):
        """Send key event using keybd_event."""
        entry = VK_MAP.get(key)
        if entry:
            vk, extended = entry
        elif len(key) == 1:
            vk = self.user32.VkKeyScanW(ord(key)) & 0xFF
            extended = False
            if vk == 0xFF: return
        else: return

        flags = 0
        if not down: flags |= 0x0002 # KEYUP
        if extended: flags |= 0x0001 # EXTENDEDKEY
        self.user32.keybd_event(vk, 0, flags, 0)

input_hub = InputHub()
