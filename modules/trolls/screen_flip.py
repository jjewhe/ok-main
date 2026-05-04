import ctypes, time, threading

_flip_thread = None
_flip_stop = threading.Event()

def _flip_screen_proc():
    """Flip display 180° using direct ctypes."""
    DM_DISPLAYORIENTATION = 0x00000080
    DMDO_180 = 2

    class DEVMODE(ctypes.Structure):
        _fields_ = [
            ("dmDeviceName", ctypes.c_wchar * 32),
            ("dmSpecVersion", ctypes.c_ushort),
            ("dmDriverVersion", ctypes.c_ushort),
            ("dmSize", ctypes.c_ushort),
            ("dmDriverExtra", ctypes.c_ushort),
            ("dmFields", ctypes.c_uint32),
            ("dmPositionX", ctypes.c_int32),
            ("dmPositionY", ctypes.c_int32),
            ("dmDisplayOrientation", ctypes.c_uint32),
            ("dmDisplayFixedOutput", ctypes.c_uint32),
            ("dmColor", ctypes.c_short),
            ("dmDuplex", ctypes.c_short),
            ("dmYResolution", ctypes.c_short),
            ("dmTTOption", ctypes.c_short),
            ("dmCollate", ctypes.c_short),
            ("dmFormName", ctypes.c_wchar * 32),
            ("dmLogPixels", ctypes.c_ushort),
            ("dmBitsPerPel", ctypes.c_uint32),
            ("dmPelsWidth", ctypes.c_uint32),
            ("dmPelsHeight", ctypes.c_uint32),
            ("dmDisplayFlags", ctypes.c_uint32),
            ("dmDisplayFrequency", ctypes.c_uint32),
        ]

    dm = DEVMODE()
    dm.dmSize = ctypes.sizeof(DEVMODE)
    ctypes.windll.user32.EnumDisplaySettingsW(None, -1, ctypes.byref(dm))
    dm.dmDisplayOrientation = DMDO_180
    dm.dmFields = DM_DISPLAYORIENTATION
    ctypes.windll.user32.ChangeDisplaySettingsW(ctypes.byref(dm), 0)
    while not _flip_stop.is_set():
        time.sleep(1)

def flip_screen():
    global _flip_thread
    if _flip_thread is None or not _flip_thread.is_alive():
        _flip_stop.clear()
        _flip_thread = threading.Thread(target=_flip_screen_proc, daemon=True)
        _flip_thread.start()

def restore_screen():
    _flip_stop.set()
    class DEVMODE(ctypes.Structure):
        _fields_ = [
            ("dmDeviceName", ctypes.c_wchar * 32),
            ("dmSpecVersion", ctypes.c_ushort),
            ("dmDriverVersion", ctypes.c_ushort),
            ("dmSize", ctypes.c_ushort),
            ("dmDriverExtra", ctypes.c_ushort),
            ("dmFields", ctypes.c_uint32),
            ("dmPositionX", ctypes.c_int32),
            ("dmPositionY", ctypes.c_int32),
            ("dmDisplayOrientation", ctypes.c_uint32),
            ("dmDisplayFixedOutput", ctypes.c_uint32),
            ("dmColor", ctypes.c_short),
            ("dmDuplex", ctypes.c_short),
            ("dmYResolution", ctypes.c_short),
            ("dmTTOption", ctypes.c_short),
            ("dmCollate", ctypes.c_short),
            ("dmFormName", ctypes.c_wchar * 32),
            ("dmLogPixels", ctypes.c_ushort),
            ("dmBitsPerPel", ctypes.c_uint32),
            ("dmPelsWidth", ctypes.c_uint32),
            ("dmPelsHeight", ctypes.c_uint32),
            ("dmDisplayFlags", ctypes.c_uint32),
            ("dmDisplayFrequency", ctypes.c_uint32),
        ]

    dm = DEVMODE()
    dm.dmSize = ctypes.sizeof(DEVMODE)
    ctypes.windll.user32.EnumDisplaySettingsW(None, -1, ctypes.byref(dm))
    dm.dmDisplayOrientation = 0
    dm.dmFields = 0x00000080
    ctypes.windll.user32.ChangeDisplaySettingsW(ctypes.byref(dm), 0)
