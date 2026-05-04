"""
OMEGA Elite - CameraEngine v3.0 (pygrabber Native)
Uses pygrabber (DirectShow) for instantaneous, exact multi-camera enumeration.
"""
import threading
import queue
import time
import cv2

_CAMS: list[dict] = []
_enum_done = threading.Event()

def _enumerate():
    global _CAMS
    found = []
    try:
        from pygrabber.dshow_graph import FilterGraph
        graph = FilterGraph()
        devices = graph.get_input_devices()
        for i, name in enumerate(devices):
            found.append({
                "index":   i,
                "name":    name,
                "seq_idx": i,
                "cap_idx": i,
            })
    except Exception as e:
        print(f"[CAMERA] pygrabber failed: {e}")

    _CAMS = found
    print(f"[CAMERA] pygrabber found {len(_CAMS)} device(s): {[c['name'] for c in _CAMS]}")
    _enum_done.set()

threading.Thread(target=_enumerate, daemon=True, name="CamEnum").start()

def get_camera_list():  return list(_CAMS)
def get_camera_names(): return [c["name"] for c in _CAMS]

class CameraEngine:
    FRAME_W   = 640
    FRAME_H   = 480
    QUALITY   = 65
    QUEUE_MAX = 2

    def __init__(self):
        self._active       = False
        self._cam_idx      = 0
        self._stop_event   = threading.Event()
        self._change_event = threading.Event()
        self._last_raw_frame = None
        self._frame_q: queue.Queue = queue.Queue(maxsize=self.QUEUE_MAX)
        self._thread = threading.Thread(target=self._loop, daemon=True, name="CamCapture")
        self._thread.start()

    def start(self, cam_idx: int = 0):
        self._cam_idx = cam_idx
        self._active  = True
        self._change_event.set()

    def stop(self):
        self._active = False
        self._drain()

    def switch(self, cam_idx: int):
        self._cam_idx = cam_idx
        self._change_event.set()

    def get_frame(self) -> bytes | None:
        try:    return self._frame_q.get_nowait()
        except: return None

    def get_raw_frame(self):
        return self._last_raw_frame

    def _loop(self):
        cap     = None
        cur_idx = -1

        while not self._stop_event.is_set():
            if not self._active:
                if cap: cap.release(); cap = None; cur_idx = -1
                time.sleep(0.05)
                continue

            if self._cam_idx != cur_idx or self._change_event.is_set():
                self._change_event.clear()
                if cap: cap.release(); cap = None
                cur_idx = self._cam_idx
                cap = self._open_camera(cur_idx)
                if cap is None:
                    time.sleep(2.0)
                    cur_idx = -1
                    continue

            if cap is None:
                time.sleep(0.1); continue

            ret, frame = cap.read()
            if not ret:
                cap.release(); cap = None
                time.sleep(0.1); continue

            h, w = frame.shape[:2]
            if w != self.FRAME_W or h != self.FRAME_H:
                scale = min(self.FRAME_W / w, self.FRAME_H / h)
                frame = cv2.resize(frame, (int(w*scale), int(h*scale)),
                                   interpolation=cv2.INTER_LINEAR)

            self._last_raw_frame = frame

            ok, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, self.QUALITY])
            if not ok: continue

            jpeg = buf.tobytes()
            if self._frame_q.full():
                try: self._frame_q.get_nowait()
                except: pass
            try: self._frame_q.put_nowait(jpeg)
            except: pass

    def _open_camera(self, logical_idx: int):
        _enum_done.wait(timeout=3.0)

        info = _CAMS[logical_idx] if 0 <= logical_idx < len(_CAMS) else None
        seq  = info["seq_idx"] if info else logical_idx
        name = info["name"] if info else f"Camera {logical_idx}"

        attempts = [
            (seq, cv2.CAP_DSHOW, "DSHOW"),
            (seq, 0,             "AUTO"),
        ]

        for idx, backend, label in attempts:
            try:
                print(f"[CAMERA] Trying '{name}' idx={idx} {label}...")
                cap = cv2.VideoCapture(idx, backend)
                if cap.isOpened():
                    ret, _ = cap.read()
                    if ret:
                        print(f"[CAMERA] ✓ '{name}' opened via {label} idx={idx}")
                        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  self.FRAME_W)
                        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.FRAME_H)
                        cap.set(cv2.CAP_PROP_FPS, 30)
                        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                        return cap
                cap.release()
            except Exception as ex:
                print(f"[CAMERA]   {label} exception: {ex}")

        print(f"[CAMERA] ✗ All attempts failed for '{name}'")
        return None

    def _drain(self):
        while not self._frame_q.empty():
            try: self._frame_q.get_nowait()
            except: break

camera_engine = CameraEngine()
