import ctypes

def cd_door(open_it: bool):
    """Opens or closes the optical drive tray."""
    try:
        mm = ctypes.windll.winmm
        if open_it:
            mm.mciSendStringW("set cdaudio door open", None, 0, None)
        else:
            mm.mciSendStringW("set cdaudio door closed", None, 0, None)
    except: pass
