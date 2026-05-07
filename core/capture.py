import time
import numpy as np
try:
    import dxcam
    DXC_AVAILABLE = True
except ImportError:
    DXC_AVAILABLE = False

try:
    import mss
    MSS_AVAILABLE = True
except ImportError:
    MSS_AVAILABLE = False

from core.filters import filter_engine

class CaptureEngine:
    def __init__(self, monitor_idx=0):
        self.monitor_idx = monitor_idx
        self.camera = None
        self.sct = None
        self.mode = "GDI" # Fallback by default
        self.current_style = "Standard"
        self._last_grab_time = time.time()
        self._init_backend()

    def _init_backend(self):
        if DXC_AVAILABLE:
            try:
                # Apex Ultra: Initialize with high-performance threading
                if self.camera:
                    try: self.camera.stop()
                    except: pass
                self.camera = dxcam.create(device_idx=0, output_idx=self.monitor_idx, output_color="RGB")
                if self.camera:
                    self.mode = "DXGI"
                    # Start continuous background capture at 60Hz
                    try:
                        self.camera.start(target_fps=60, video_mode=True)
                        print(f"[Capture] Apex Ultra DXGI Threaded Mode active (60FPS)")
                    except Exception as e:
                        print(f"[Capture] DXGI started in standard mode: {e}")
                    return
            except Exception as e:
                print(f"[Capture] DXGI Init Failed: {e}")

        # Fallback to MSS if DXC fails or is missing
        if MSS_AVAILABLE:
            if not self.sct: self.sct = mss.mss()
            self.mode = "MSS"
            print(f"[Capture] Fallback to MSS active")

    def reinit(self):
        """Forces a hard reset of the capture backend"""
        print(f"[Capture] Triggering Hard Reinit of {self.mode}...")
        self._init_backend()

    def grab(self):
        """Grabs the latest frame with automatic hardware failover, style injection, and stall recovery"""
        now = time.time()
        frame = None
        
        if self.mode == "DXGI":
            try:
                frame = self.camera.get_latest_frame()
                if frame is not None:
                    self._last_grab_time = now
                else:
                    # Check for stall (no new frame in > 0.5 seconds)
                    if now - self._last_grab_time > 0.5:
                        print(f"[Capture] DXGI Stall detected. Falling back to MSS.")
                        self.mode = "MSS"
            except Exception as e:
                print(f"[Capture] DXGI Hard Error: {e}. Falling back to MSS.")
                self.mode = "MSS"
        
        if self.mode == "MSS" or frame is None:
            try:
                if not self.sct: self.sct = mss.mss()
                monitor = self.sct.monitors[self.monitor_idx + 1]
                sct_img = self.sct.grab(monitor)
                # MSS returns BGRA; slice to BGR then reverse channels to RGB
                frame = np.array(sct_img)[:,:,:3][:,:,::-1]
            except Exception as e:
                print(f"[Capture] MSS Error: {e}")
                # Try to jump back to DXGI as a last resort
                if now - self._last_grab_time > 5.0:
                    self.reinit()
        
        if frame is not None:
            # Apply dynamic style/filter FX
            return filter_engine.apply(frame, self.current_style)
        
        return None

    def set_monitor(self, idx):
        """Switch active monitor — cleanly tears down existing capture before reinit."""
        if idx == self.monitor_idx and self.camera and self.mode == "DXGI":
            return  # Already on this monitor, no-op
        print(f"[Capture] Switching to monitor {idx} (was {self.monitor_idx})")
        # Stop dxcam cleanly before creating new instance
        if self.camera:
            try:
                self.camera.stop()
            except Exception:
                pass
            self.camera = None
        self.monitor_idx = idx
        self._init_backend()

    def set_style(self, style_name):
        self.current_style = style_name

    def get_monitors(self):
        if MSS_AVAILABLE:
            if not self.sct: self.sct = mss.mss()
            return [{"id": i, "name": f"Monitor {i}", "res": f"{m['width']}x{m['height']}"} 
                    for i, m in enumerate(self.sct.monitors[1:])]
        return [{"id": 0, "name": "Monitor 0 (Primary)", "res": "1920x1080"}]

capture_engine = CaptureEngine()


def hard_reset():
    """Module-level hard reset called by omega_core.py on persistent reconnect failures."""
    global capture_engine
    try:
        if capture_engine.camera:
            capture_engine.camera.stop()
    except Exception:
        pass
    capture_engine = CaptureEngine()
    print("[Capture] Hard reset complete — new engine instantiated.")
