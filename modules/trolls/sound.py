import os, tempfile, urllib.request, ctypes, threading, base64

def play_loop(url):
    """Downloads and plays a sound on a continuous loop."""
    def _play():
        try:
            fd, p = tempfile.mkstemp(suffix=".mp3")
            os.close(fd)
            urllib.request.urlretrieve(url, p)
            mm = ctypes.windll.winmm
            mm.mciSendStringW("close snd", None, 0, None)
            mm.mciSendStringW(f'open "{p}" type mpegvideo alias snd', None, 0, None)
            mm.mciSendStringW("play snd repeat", None, 0, None)
        except Exception: pass

    threading.Thread(target=_play, daemon=True).start()

def stop_all_sounds():
    """Stops all currently playing sounds (MCI and Pygame)."""
    def _stop():
        try:
            ctypes.windll.winmm.mciSendStringW("stop snd", None, 0, None)
            ctypes.windll.winmm.mciSendStringW("close snd", None, 0, None)
            ctypes.windll.winmm.mciSendStringW("stop snd2", None, 0, None)
            ctypes.windll.winmm.mciSendStringW("close snd2", None, 0, None)
        except: pass
        try:
            import pygame
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except: pass

    threading.Thread(target=_stop, daemon=True).start()

def play_base64_audio(b64_data, filename):
    """Decodes and plays base64 audio data."""
    def _play():
        nonlocal b64_data
        try:
            missing = len(b64_data) % 4
            if missing: b64_data += "=" * (4 - missing)
            raw = base64.b64decode(b64_data)
            ext = os.path.splitext(filename)[1] or ".mp3"
            fd, p = tempfile.mkstemp(suffix=ext)
            os.write(fd, raw)
            os.close(fd)
            mm = ctypes.windll.winmm
            mm.mciSendStringW("close snd2", None, 0, None)
            mm.mciSendStringW(f'open "{p}" type mpegvideo alias snd2', None, 0, None)
            mm.mciSendStringW("play snd2", None, 0, None)
        except: pass

    threading.Thread(target=_play, daemon=True).start()
