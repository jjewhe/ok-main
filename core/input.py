import ctypes
from ctypes import wintypes
import time

# Low-level Windows API constants
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008

# C-style structural definitions
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD), 
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD), 
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]

class INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]

class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", INPUT_UNION)]

# Key mappings (Inter -> Virtual Key Code)
VK_MAP = {
    "Enter": 0x0D, "Backspace": 0x08, "Tab": 0x09, "Shift": 0x10, "Control": 0x11, "Alt": 0x12,
    "Escape": 0x1b, " ": 0x20, "ArrowLeft": 0x25, "ArrowUp": 0x26, "ArrowRight": 0x27, "ArrowDown": 0x28,
    "Delete": 0x2e, "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73, "F5": 0x74, "F6": 0x75, "F7": 0x76,
}

class InputHub:
    def __init__(self):
        self.user32 = ctypes.windll.user32
        self.screen_width = self.user32.GetSystemMetrics(0)
        self.screen_height = self.user32.GetSystemMetrics(1)

    def mouse_move(self, x, y):
        """Move mouse to absolute pixel location (x, y)"""
        # Normalize to 65535 for MOUSEEVENTF_ABSOLUTE
        norm_x = int(x * 65535 / (self.screen_width - 1))
        norm_y = int(y * 65535 / (self.screen_height - 1))
        
        mi = MOUSEINPUT(norm_x, norm_y, 0, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, 0, None)
        inp = INPUT(INPUT_MOUSE, INPUT_UNION(mi=mi))
        self.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

    def mouse_click(self, btn="left", down=True):
        """Send mouse button down/up event"""
        flags = 0
        if btn == "left": flags = MOUSEEVENTF_LEFTDOWN if down else MOUSEEVENTF_LEFTUP
        else: flags = MOUSEEVENTF_RIGHTDOWN if down else MOUSEEVENTF_RIGHTUP
        
        mi = MOUSEINPUT(0, 0, 0, flags, 0, None)
        inp = INPUT(INPUT_MOUSE, INPUT_UNION(mi=mi))
        self.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

    def key_event(self, key, down=True):
        """Send virtual key down/up event"""
        vk = VK_MAP.get(key)
        if not vk:
            if len(key) == 1: vk = ord(key.upper())
            else: return # Unknown composite key
            
        flags = 0 if down else KEYEVENTF_KEYUP
        ki = KEYBDINPUT(vk, 0, flags, 0, None)
        inp = INPUT(INPUT_KEYBOARD, INPUT_UNION(ki=ki))
        self.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

input_hub = InputHub()
